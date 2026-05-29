# backend/packages/harness/deerflow/tools/nail/action_proposal.py
"""将运营方案写入 DB，标记 pending，等待人工确认。"""
import json
import logging
import uuid

from langchain.tools import tool

from .base import get_db

logger = logging.getLogger(__name__)


@tool
def action_proposal_tool(proposal_json: str, run_id: str = "") -> str:
    """将单条运营方案写入 action_proposals 表，等待人工确认后执行。

    Args:
        proposal_json: 单条运营方案的 JSON 字符串（ops_analysis_tool 返回的 marketing_actions 中的一项），
                       或包含 marketing_actions 数组的完整 JSON（自动取第一条）。
        run_id: 关联的 Agent run ID（可选）。

    Returns:
        JSON 字符串，字段：
        - proposal_id (str): 新生成的提案 ID
        - status (str): "pending"
        - title (str): 方案标题
        - message (str): 提示文字
        - requires_human_confirm (bool): 始终为 true
    """
    try:
        data = json.loads(proposal_json)

        # 兼容：传入整个 ops_analysis_tool 返回或单条 action
        if isinstance(data, dict) and "marketing_actions" in data:
            actions = data["marketing_actions"]
            proposal = actions[0] if actions else {}
        elif isinstance(data, list):
            proposal = data[0] if data else {}
        else:
            proposal = data

        proposal_id = str(uuid.uuid4())
        title = proposal.get("title", "运营方案")

        with get_db() as conn:
            conn.execute(
                "INSERT INTO action_proposals (id, run_id, title, content, status) VALUES (?, ?, ?, ?, 'pending')",
                (proposal_id, run_id or "", title, json.dumps(proposal, ensure_ascii=False))
            )
            conn.commit()

        logger.info("ActionProposal created: %s (%s)", proposal_id, title)

        return json.dumps({
            "proposal_id": proposal_id,
            "status": "pending",
            "title": title,
            "message": f"方案「{title}」已生成，等待运营人员在看板确认后执行。",
            "requires_human_confirm": True,
        }, ensure_ascii=False)

    except Exception as e:
        logger.error("ActionProposal failed: %s", e)
        return json.dumps({
            "error": str(e),
            "proposal_id": "",
            "status": "failed",
            "title": "",
            "message": f"方案创建失败：{e}",
            "requires_human_confirm": False,
        }, ensure_ascii=False)
