# backend/packages/harness/deerflow/tools/nail/customer_service.py
"""美甲客服：处理咨询/预约/售后，回答必须标注信息来源。"""
import json
import logging

from langchain.tools import tool
from langchain_core.messages import HumanMessage

logger = logging.getLogger(__name__)

_STORE_SOP = """
【门店规则 - 来自门店 SOP】
- 营业时间：每日 10:00-21:00（周一至周日）
- 预约规则：至少提前 2 小时预约，微信/APP 均可
- 价格区间：基础款 ¥99-199，猫眼款 +¥30，延甲 +¥50-100
- 退款政策：未开工可全退，开工后不退
- 脱落保修：7 天内免费补色，超期需补差价
- 常见问题：猫眼胶需加 ¥30；凝胶甲保持约 3-4 周
"""


@tool
def customer_service_tool(user_question: str, user_id: str = "") -> str:
    """处理用户美甲咨询，回复附信息来源标注。

    Args:
        user_question: 用户的问题。
        user_id: 用户 ID（可选，用于个性化回复）。

    Returns:
        JSON 字符串，字段：
        - reply (str): 客服回复
        - source (str): 信息来源标注
        - needs_human (bool): 是否需要转人工
    """
    try:
        from deerflow.models import create_chat_model
        model = create_chat_model(thinking_enabled=False, attach_tracing=False)

        prompt = (
            f"你是专业美甲门店客服，回复简洁亲切，引用规则时标注来源。\n"
            f"{_STORE_SOP}\n"
            f"用户问题：{user_question}\n"
            '返回JSON：{"reply":"回复内容","source":"来自门店 SOP / 来自近期趋势 / 来自用户偏好","needs_human":false}'
        )
        resp = model.invoke([HumanMessage(content=prompt)])
        raw = resp.content.strip()
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        result = json.loads(raw.strip())
        return json.dumps(result, ensure_ascii=False)

    except Exception as e:
        logger.warning("CustomerService LLM fallback: %s", e)
        # 规则匹配降级
        reply = "您好！"
        source = "来自门店 SOP"
        if "预约" in user_question:
            reply = "预约请至少提前 2 小时，营业时间 10:00-21:00，微信或 APP 均可预约。（来自门店 SOP）"
        elif "价格" in user_question or "多少钱" in user_question:
            reply = "基础款 ¥99-199，猫眼款加 ¥30，延甲加 ¥50-100。（来自门店 SOP）"
        elif "退款" in user_question or "退单" in user_question:
            reply = "未开工前可全额退款，开工后无法退款，请知悉。（来自门店 SOP）"
        elif "脱落" in user_question or "保修" in user_question:
            reply = "7 天内脱落可免费补色，超期补色需补差价。（来自门店 SOP）"
        else:
            reply = f"您的问题我已记录，将由人工客服跟进解答。"
            source = "人工转接"
        return json.dumps({"reply": reply, "source": source, "needs_human": "人工" in reply}, ensure_ascii=False)
