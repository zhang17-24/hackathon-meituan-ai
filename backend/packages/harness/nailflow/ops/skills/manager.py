"""SkillManager — 技能生命周期管理 + Agent 上下文注入。"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from .loader import SkillLoader
from .models import Skill

logger = logging.getLogger(__name__)


class SkillManager:
    """管理技能加载、注入 Agent 上下文、执行记录。

    注入格式对齐 OpenClaw 的 formatSkillsForPrompt() XML 布局。
    """

    def __init__(self, loader: SkillLoader | None = None):
        self._loader = loader or SkillLoader()
        self._cache: dict[str, list[Skill]] = {}

    def load_skills(self, groups: list[str] | None = None) -> list[Skill]:
        """加载技能，按 group 过滤。"""
        cache_key = ",".join(sorted(groups)) if groups else "all"
        if cache_key not in self._cache:
            all_skills = self._loader.load_all()
            if groups:
                group_set = set(groups)
                all_skills = [s for s in all_skills if s.group in group_set]
            self._cache[cache_key] = all_skills
        return self._cache[cache_key]

    def find_skill(self, name: str) -> Skill | None:
        for s in self.load_skills():
            if s.name == name:
                return s
        return None

    def inject_context(self, skills: list[Skill]) -> str:
        """将技能列表格式化为 system prompt 可追加的 XML 块。

        格式与 OpenClaw 的 formatSkillsForPrompt() 对齐。
        """
        if not skills:
            return ""

        lines = [
            "",
            "The following skills provide specialized instructions for specific tasks.",
            "When a skill matches the task, follow its steps using the listed tools.",
            "",
            "<available_skills>",
        ]
        for skill in skills:
            lines.append("  <skill>")
            lines.append(f"    <name>{self._escape_xml(skill.name)}</name>")
            lines.append(f"    <description>{self._escape_xml(skill.description)}</description>")
            if skill.tools:
                tools_str = ", ".join(skill.tools)
                lines.append(f"    <tools>{self._escape_xml(tools_str)}</tools>")
            lines.append("    <instructions>")
            body_short = skill.body[:2000]
            lines.append(self._escape_xml(body_short))
            lines.append("    </instructions>")
            lines.append("  </skill>")
        lines.append("</available_skills>")

        return "\n".join(lines)

    def record_execution(self, skill_name: str, run_id: str | None,
                         status: str, result: str, error: str = "") -> str:
        """记录技能执行到 skill_executions 表。返回 execution_id。"""
        execution_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        try:
            from nailflow.tools.nail.base import get_db
            with get_db() as conn:
                conn.execute(
                    """INSERT INTO skill_executions (id, skill_name, run_id, status, result, error, started_at, completed_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (execution_id, skill_name, run_id, status, result, error, now, now),
                )
                conn.commit()
        except Exception as e:
            logger.warning("Failed to record skill execution: %s", e)
        return execution_id

    def invalidate_cache(self) -> None:
        self._cache.clear()

    @staticmethod
    def _escape_xml(text: str) -> str:
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
