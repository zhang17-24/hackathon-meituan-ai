# backend/packages/harness/deerflow/tools/nail/router_config.py
"""NailFlow 工具能力注册表 — 每个工具/Agent 声明所需的能力类型。

添加新工具时，只需在这里加一行，ModelRouter 自动处理模型选择。
"""
from deerflow.models.router import Capability

# ── 工具能力映射 ──
TOOL_CAPABILITIES: dict[str, Capability] = {
    # nail 组
    "unified_tryon_tool":       Capability.VISION,     # 内部用 vision 分析 + IMAGE_GEN 生图
    "hand_detect_tool":         Capability.CHAT,       # MediaPipe 本地检测，不用 LLM
    "nail_mask_tool":           Capability.CHAT,       # PIL 本地生成 mask，不用 LLM
    "style_understanding_tool": Capability.VISION,     # 必须 vision 模型看图
    "prompt_builder_tool":      Capability.CHAT,       # 纯文本 prompt 拼接，不用 LLM
    "image_generation_tool":    Capability.IMAGE_GEN,  # 生图 API
    "quality_check_tool":       Capability.VISION,     # 双图对比需要 vision
    "preference_rag_tool":      Capability.CHAT,       # ChromaDB 向量检索，不用 LLM
    "trend_query_tool":         Capability.CHAT,       # SQL 聚合查询，不用 LLM
    "nail_style_recommend_tool": Capability.CHAT,      # 向量推荐，不用 LLM
    "nail_run_query_tool":      Capability.CHAT,       # DB 查询，不用 LLM
    "user_pref_analytics_tool": Capability.CHAT,       # 分析统计，不用 LLM

    # nail_ops 组
    "trend_discovery_tool":     Capability.CHAT,       # LLM 趋势洞察
    "ops_analysis_tool":        Capability.CHAT,       # LLM 营销方案
    "customer_service_tool":    Capability.CHAT,       # LLM 客服
    "action_proposal_tool":     Capability.CHAT,       # DB 写入，不用 LLM

    # nail_dev 组
    "evaluation_tool":          Capability.CHAT,       # LLM 评分

    # Agent
    "lead_agent":               Capability.CHAT,       # 主 Agent
}

# ── 能力 → DB 字段映射 ──
CAPABILITY_DB_FILTER: dict[Capability, str] = {
    Capability.CHAT:     "",  # 无特殊过滤
    Capability.VISION:   "supports_vision = 1",
    Capability.IMAGE_GEN: "",  # 通过 _model_matches_capability 启发式匹配
}
