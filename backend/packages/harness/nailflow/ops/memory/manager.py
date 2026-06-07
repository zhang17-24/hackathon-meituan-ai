"""MemoryManager — SOUL.md 加载 + MEMORY.md 读写 + SQLite 记忆管理。"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from .models import MemoryEntry, MemoryType

logger = logging.getLogger(__name__)

_SOUL_PATH = Path(__file__).resolve().parent / "soul.md"
_MEMORY_MD_PATH = Path("data/memory/MEMORY.md")
_MAX_MEMORIES = 200  # 触发总结的阈值
_INJECT_LIMIT = 20   # 注入 Agent 上下文的最大条数


class MemoryManager:
    """管理 Agent 持久化记忆。"""

    def load_soul(self) -> str:
        """读取 SOUL.md 运营专家人设。"""
        if _SOUL_PATH.exists():
            return _SOUL_PATH.read_text(encoding="utf-8")
        logger.warning("SOUL.md not found at %s", _SOUL_PATH)
        return ""

    def load_memories(self, limit: int = _INJECT_LIMIT,
                      memory_type: str | None = None) -> list[MemoryEntry]:
        """从 SQLite 读取最近记忆。"""
        try:
            from nailflow.tools.nail.base import get_db
            with get_db() as conn:
                if memory_type:
                    rows = conn.execute(
                        """SELECT id, memory_type, content, created_at
                           FROM ops_memory
                           WHERE memory_type = ?
                           ORDER BY created_at DESC LIMIT ?""",
                        (memory_type, limit),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        """SELECT id, memory_type, content, created_at
                           FROM ops_memory
                           ORDER BY created_at DESC LIMIT ?""",
                        (limit,),
                    ).fetchall()
                return [MemoryEntry(
                    id=r["id"],
                    memory_type=r["memory_type"] or "marketing",
                    content=r["content"] or "",
                    created_at=r["created_at"] or "",
                ) for r in rows]
        except Exception as e:
            logger.error("MemoryManager.load_memories failed: %s", e)
            return []

    def append(self, content: str, memory_type: str = "marketing") -> int:
        """新增一条记忆。返回记录 id。"""
        now = datetime.now(timezone.utc).isoformat()
        try:
            from nailflow.tools.nail.base import get_db
            with get_db() as conn:
                cursor = conn.execute(
                    "INSERT INTO ops_memory (memory_type, content, created_at) VALUES (?, ?, ?)",
                    (memory_type, content, now),
                )
                conn.commit()
                entry_id = cursor.lastrowid
        except Exception as e:
            logger.error("MemoryManager.append failed: %s", e)
            return -1

        # 检查是否需要总结
        try:
            from nailflow.tools.nail.base import get_db
            with get_db() as conn:
                count = conn.execute("SELECT COUNT(*) FROM ops_memory").fetchone()[0]
        except Exception:
            count = 0

        if count > _MAX_MEMORIES:
            self._summarize_old()

        # 异步更新 MEMORY.md
        try:
            self.sync_md()
        except Exception:
            pass

        return entry_id

    def sync_md(self) -> str:
        """将 SQLite 记忆同步到 MEMORY.md 文件。"""
        entries = self.load_memories(limit=100)
        if not entries:
            return ""

        # 按类型分组
        grouped: dict[str, list[MemoryEntry]] = {t.value: [] for t in MemoryType}
        for e in entries:
            mt = e.memory_type or "marketing"
            grouped.setdefault(mt, []).append(e)

        lines = ["# nailflow 运营记忆", ""]
        for mem_type, items in grouped.items():
            if not items:
                continue
            lines.append(f"## {MemoryType(mem_type).name if mem_type in [t.value for t in MemoryType] else mem_type}")
            for item in items:
                date_str = item.created_at[:10] if item.created_at else "?"
                lines.append(f"- [{date_str}] {item.content}")
            lines.append("")

        content = "\n".join(lines)
        _MEMORY_MD_PATH.parent.mkdir(parents=True, exist_ok=True)
        _MEMORY_MD_PATH.write_text(content, encoding="utf-8")
        return content

    def inject_context(self) -> str:
        """生成注入 Agent 上下文的记忆块。

        格式：SOUL.md 全量 + 最近记忆列表。
        """
        parts: list[str] = []

        soul = self.load_soul()
        if soul:
            parts.append(soul)

        memories = self.load_memories(limit=_INJECT_LIMIT)
        if memories:
            lines = ["", "## 运营记忆（最近）"]
            for m in memories:
                date_str = m.created_at[:10] if m.created_at else "?"
                lines.append(f"- [{date_str}] [{m.memory_type}] {m.content}")
            parts.append("\n".join(lines))

        return "\n\n".join(parts)

    def _summarize_old(self) -> None:
        """LLM 压缩旧记忆为摘要。"""
        try:
            from nailflow.models import create_chat_model

            from nailflow.tools.nail.base import get_db
            with get_db() as conn:
                old_rows = conn.execute(
                    """SELECT id, memory_type, content FROM ops_memory
                       ORDER BY created_at ASC LIMIT 100"""
                ).fetchall()
                if not old_rows:
                    return

            old_text = "\n".join(f"- [{r['memory_type']}] {r['content']}" for r in old_rows)
            model = create_chat_model(thinking_enabled=False, attach_tracing=False)
            from langchain_core.messages import HumanMessage

            prompt = (
                "将以下美甲运营记忆压缩为3-5条关键摘要（返回中文，每条一行）：\n\n"
                + old_text
            )
            resp = model.invoke([HumanMessage(content=prompt)])
            summary_text = resp.content.strip()

            # 删除旧条目，写入摘要
            with get_db() as conn:
                old_ids = [r["id"] for r in old_rows]
                placeholders = ",".join("?" for _ in old_ids)
                conn.execute(f"DELETE FROM ops_memory WHERE id IN ({placeholders})", old_ids)
                now = datetime.now(timezone.utc).isoformat()
                conn.execute(
                    "INSERT INTO ops_memory (memory_type, content, created_at) VALUES (?, ?, ?)",
                    ("marketing", f"[摘要] {summary_text}", now),
                )
                conn.commit()
            logger.info("Memory summarized: %d old entries → 1 summary", len(old_rows))
        except Exception as e:
            logger.warning("Memory summarization failed (non-fatal): %s", e)
