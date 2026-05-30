# backend/packages/harness/deerflow/tools/nail/evaluation.py
"""按赛题评分体系对本次 NailFlow 运行进行自动评分（dev 角色专用）。"""
import json
import logging
import uuid

from langchain.tools import tool
from langchain_core.messages import HumanMessage

from .base import get_db

logger = logging.getLogger(__name__)

_RUBRIC = """
【NailFlow 黑客松评分标准（总分 100 分）】
1. 完整性（30分）：用户端流程覆盖（上传-选款-试戴-解释-推荐）；运营端流程覆盖（趋势-建议-确认-执行）；至少覆盖 3 类异常处理
2. 应用效果（25分）：甲面边界清晰、肤色一致、光照匹配、款式相似度、客服命中率、营销方案可执行率
3. 创新性（20分）：多 Agent 编排编排、RAG 偏好推荐、EvaluationAgent 自反馈、长期记忆
4. 商业价值（15分）：试戴转化率、收藏率、营销动作点击率、客服节省时间、复购推荐
5. 加分项与硬约束（10分）：生成 <30s；工具响应 <3s；端到端 <2min；README清晰；至少 3 类失败处理
"""


@tool
def evaluation_tool(run_summary: str, run_id: str = "") -> str:
    """对本次 NailFlow 运行按赛题评分体系自动打分。

    Args:
        run_summary: 本次运行的描述（完成了哪些步骤，结果如何，遇到什么问题）。
        run_id: 关联的 run ID（用于持久化评分结果，可选）。

    Returns:
        JSON 字符串，字段：
        - total_score (int): 总分 0-100
        - rubric_scores (dict): 分项分数（completeness/application_effect/innovation/business_value/hard_constraints）
        - blocking_issues (list): 必须修复的问题列表
        - next_dev_tasks (list): 下一步开发任务，每项含 task/score_gain/effort
        - demo_evidence (list): 答辩可展示的证据列表
    """
    _default = {
        "total_score": 60,
        "rubric_scores": {"completeness": 18, "application_effect": 15, "innovation": 12, "business_value": 9, "hard_constraints": 6},
        "blocking_issues": ["EvaluationAgent LLM 调用失败，请配置 API Key"],
        "next_dev_tasks": [{"task": "配置并测试 LLM API", "score_gain": 10, "effort": "low"}],
        "demo_evidence": ["工具链结构完整（13 个工具注册）", "三端鉴权已实现"],
    }

    try:
        from deerflow.models import create_chat_model
        from deerflow.models.router import ModelRouter, Capability
        resolution = ModelRouter.resolve("evaluation_tool", Capability.CHAT)
        model = create_chat_model(name=resolution.name if resolution else None, thinking_enabled=False, attach_tracing=False)

        prompt = (
            f"你是 NailFlow 系统的自动评测 Agent。按以下评分标准对本次运行打分，返回 JSON。\n"
            f"{_RUBRIC}\n"
            f"本次运行描述：{run_summary}\n"
            '返回格式（只返回 JSON）：\n'
            '{"total_score":75,"rubric_scores":{"completeness":22,"application_effect":18,"innovation":15,"business_value":12,"hard_constraints":8},'
            '"blocking_issues":["必须修复的问题"],"next_dev_tasks":[{"task":"任务描述","score_gain":5,"effort":"low|medium|high"}],'
            '"demo_evidence":["答辩证据1"]}'
        )
        resp = model.invoke([HumanMessage(content=prompt)])
        raw = resp.content.strip()
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        result = json.loads(raw.strip())

    except Exception as e:
        logger.warning("EvaluationTool LLM fallback: %s", e)
        result = _default

    # 持久化评分结果
    if run_id:
        try:
            with get_db() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO evaluation_results "
                    "(id, run_id, total_score, rubric_scores, blocking_issues, next_dev_tasks) "
                    "VALUES (?,?,?,?,?,?)",
                    (
                        str(uuid.uuid4()),
                        run_id,
                        result.get("total_score", 0),
                        json.dumps(result.get("rubric_scores", {})),
                        json.dumps(result.get("blocking_issues", [])),
                        json.dumps(result.get("next_dev_tasks", [])),
                    )
                )
                conn.commit()
        except Exception as db_err:
            logger.warning("Failed to persist evaluation result: %s", db_err)

    return json.dumps(result, ensure_ascii=False)
