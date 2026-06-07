"""MemoryInjector — LangGraph 中间件，在 Agent 每次 run 时注入记忆上下文。

注册位置：nailflow 中间件栈的 SummarizationMiddleware 之后、ClarificationMiddleware 之前。
"""
from __future__ import annotations

import logging
from typing import Any

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import SystemMessage

logger = logging.getLogger(__name__)


class MemoryInjectorMiddleware(AgentMiddleware):
    """在 Agent run 开始时注入 SOUL.md + 最近记忆到消息列表。"""

    def __init__(self, memory_manager=None):
        super().__init__()
        self._memory_manager = memory_manager

    def _get_manager(self):
        if self._memory_manager is not None:
            return self._memory_manager
        from nailflow.ops.memory.manager import MemoryManager
        return MemoryManager()

    def before_model(self, state: dict[str, Any], runtime: Any) -> dict[str, Any] | None:
        """在每次 LLM 调用前检查是否需要注入记忆。

        仅在对话开始（无 SystemMessage 或以 SystemMessage 开头但无记忆标记时）注入。
        """
        messages = state.get("messages", [])
        if not messages:
            return None

        # 检查是否已注入记忆（避免重复注入）
        for msg in messages:
            if isinstance(msg, SystemMessage) and "nailflow 运营记忆" in str(msg.content):
                return None

        try:
            mgr = self._get_manager()
            context = mgr.inject_context()
            if not context:
                return None

            # 在消息列表开头插入记忆上下文
            memory_msg = SystemMessage(content=context)
            state["messages"] = [memory_msg] + list(messages)
            logger.debug("Memory injected: %d chars", len(context))
        except Exception:
            logger.debug("Memory injection skipped (non-fatal)")

        return None  # 返回 None 让中间件链继续
