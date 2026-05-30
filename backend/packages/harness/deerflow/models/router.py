"""ModelRouter — 通用模型路由层。

所有调用方（tool / agent / subagent）统一通过此入口解析模型，
不再各自实现优先级链。

优先级: user_preference > tool_override > agent_config > capability_match > config_fallback > db_fallback

Usage:
    from deerflow.models.router import ModelRouter, Capability

    resolution = ModelRouter.resolve("style_understanding_tool", Capability.VISION)
    model = create_chat_model(name=resolution.name, ...)
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class Capability(str, Enum):
    CHAT = "chat"
    VISION = "vision"
    IMAGE_GEN = "image_gen"


@dataclass
class ModelResolution:
    name: str
    model_id: str = ""   # 实际 API 调用的模型标识，如 doubao-seedream-5-0-260128
    source: str = ""     # "user" | "tool_override" | "agent_config" | "capability_match" | "config_fallback" | "db_fallback"
    supports_vision: bool = False
    api_key: str | None = None
    api_base: str | None = None
    use_class: str = "langchain_openai:ChatOpenAI"
    extra: dict = field(default_factory=dict)


def _get_db_models(active_only: bool = True) -> list[dict]:
    """读取 nail_model_configs 中所有模型配置。"""
    try:
        from packages.harness.deerflow.tools.nail.base import get_db
        with get_db() as conn:
            where = "WHERE is_active = 1" if active_only else ""
            rows = conn.execute(
                f"SELECT name, model_id, api_key, api_base, use_class, "
                f"supports_vision, supports_thinking "
                f"FROM nail_model_configs {where} ORDER BY created_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.debug("_get_db_models: %s", e)
        return []


def _get_tool_override(tool_name: str) -> str | None:
    """读取工具专属覆盖（仅 nail_tool_overrides，不含 tool_default）。"""
    try:
        from packages.harness.deerflow.tools.nail.base import get_db
        with get_db() as conn:
            row = conn.execute(
                "SELECT model_name FROM nail_tool_overrides "
                "WHERE tool_name = ? AND is_enabled = 1 AND model_name IS NOT NULL",
                (tool_name,),
            ).fetchone()
            return row["model_name"] if row else None
    except Exception as e:
        logger.debug("_get_tool_override(%s): %s", tool_name, e)
        return None


def _get_agent_config() -> dict[str, str | None]:
    """读取 nail_agent_configs。"""
    try:
        from packages.harness.deerflow.tools.nail.base import get_db
        with get_db() as conn:
            rows = conn.execute(
                "SELECT config_key, model_name FROM nail_agent_configs"
            ).fetchall()
        return {r["config_key"]: r["model_name"] for r in rows}
    except Exception as e:
        logger.debug("_get_agent_config: %s", e)
        return {}


def _model_matches_capability(model: dict, capability: Capability) -> bool:
    """判断模型是否满足能力需求。"""
    if capability == Capability.VISION:
        return bool(model.get("supports_vision"))
    if capability == Capability.IMAGE_GEN:
        model_id = (model.get("model_id") or "").lower()
        use_class = (model.get("use_class") or "").lower()
        return ("seedream" in model_id or "image" in model_id or
                "dall" in model_id or "sora" in model_id or
                "seedream" in use_class)
    # CHAT: 不过滤
    return True


class ModelRouter:
    """统一模型路由器。"""

    @classmethod
    def resolve(
        cls,
        caller: str,
        capability: Capability = Capability.CHAT,
        user_preference: str | None = None,
        allow_fallback: bool = True,
    ) -> ModelResolution | None:
        """解析调用方应使用的模型。

        Returns:
            ModelResolution 或 None（当 allow_fallback=False 且无匹配时）。
        """
        # ── 优先级 1: 用户手动选择 ──
        if user_preference:
            db_models = _get_db_models()
            for m in db_models:
                if m["name"] == user_preference:
                    return _to_resolution(m, "user")
            # 也检查 config.yaml
            try:
                from deerflow.config import get_app_config
                cfg = get_app_config()
                mc = cfg.get_model_config(user_preference)
                if mc:
                    return _to_resolution({"name": mc.name, "model_id": mc.model,
                                           "use_class": mc.use,
                                           "supports_vision": mc.supports_vision,
                                           "api_key": None, "api_base": None}, "user")
            except Exception:
                pass

        # ── 优先级 2: 工具专属覆盖 ──
        override = _get_tool_override(caller)
        if override:
            db_models = _get_db_models()
            for m in db_models:
                if m["name"] == override:
                    return _to_resolution(m, "tool_override")

        # ── 优先级 3: agent 配置 ──
        agent_config = _get_agent_config()
        agent_model = agent_config.get("tool_default") or agent_config.get("main_agent")
        if agent_model and capability == Capability.CHAT:
            db_models = _get_db_models()
            for m in db_models:
                if m["name"] == agent_model:
                    return _to_resolution(m, "agent_config")
        elif agent_model:
            # 非 CHAT 能力：只有匹配能力时才用 agent 配置
            db_models = _get_db_models()
            for m in db_models:
                if m["name"] == agent_model and _model_matches_capability(m, capability):
                    return _to_resolution(m, "agent_config")

        # ── 优先级 4: 能力匹配 ──
        db_models = _get_db_models()
        for m in db_models:
            if _model_matches_capability(m, capability):
                return _to_resolution(m, "capability_match")

        # ── 优先级 5: config.yaml 首个模型 ──
        try:
            from deerflow.config import get_app_config
            cfg = get_app_config()
            if cfg.models:
                mc = cfg.models[0]
                if capability == Capability.CHAT or (capability == Capability.VISION and mc.supports_vision):
                    return _to_resolution(
                        {"name": mc.name, "model_id": mc.model, "use_class": mc.use,
                         "supports_vision": mc.supports_vision, "api_key": None, "api_base": None},
                        "config_fallback",
                    )
        except Exception:
            pass

        # ── 优先级 6: DB 任意活跃模型 ──
        db_models = _get_db_models()
        if db_models:
            return _to_resolution(db_models[0], "db_fallback")

        # ── 无可用模型 ──
        if allow_fallback:
            return None
        return None

    @classmethod
    def resolve_for_image_gen(cls, caller: str) -> ModelResolution | None:
        """image_generation_tool 专用：解析模型 + api_key + api_base。"""
        resolution = cls.resolve(caller, Capability.IMAGE_GEN)
        if resolution and resolution.api_key and resolution.api_base:
            return resolution
        # 尝试 IMAGE_GEN 能力匹配的模型
        return cls.resolve(caller, Capability.IMAGE_GEN, allow_fallback=True)


def _to_resolution(model: dict, source: str) -> ModelResolution:
    return ModelResolution(
        name=model["name"],
        model_id=model.get("model_id") or model["name"],
        source=source,
        supports_vision=bool(model.get("supports_vision")),
        api_key=model.get("api_key") or None,
        api_base=model.get("api_base") or None,
        use_class=model.get("use_class") or "langchain_openai:ChatOpenAI",
    )
