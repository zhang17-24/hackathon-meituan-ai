# ops_channel/delivery/adapters/file_adapter.py
"""文件输出适配器：将 FileMessage 写入磁盘。"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from ..base import AbstractChannelAdapter, ChannelCapability, DeliveryResult, DeliveryTarget

if TYPE_CHECKING:
    from ..messages.base import FileMessage, AbstractMessage

logger = logging.getLogger(__name__)


class FileAdapter(AbstractChannelAdapter):
    def __init__(self, config: dict | None = None):
        cfg = config or {}
        self._output_dir = Path(cfg.get("output_dir", "data/reports"))

    @property
    def channel_id(self) -> str:
        return "file"

    @property
    def capabilities(self) -> ChannelCapability:
        return ChannelCapability.FILE

    async def send(self, target: DeliveryTarget, message: "AbstractMessage") -> DeliveryResult:
        from ..messages.base import FileMessage

        if not isinstance(message, FileMessage):
            return DeliveryResult(ok=False, channel="file",
                error=f"FileAdapter expects FileMessage, got {type(message).__name__}")

        out_dir = Path(target.recipient) if target.recipient else self._output_dir
        out_dir.mkdir(parents=True, exist_ok=True)

        filepath = out_dir / message.filename
        try:
            filepath.write_bytes(message.content)
            logger.info("FileAdapter: saved %s (%d bytes)", filepath, len(message.content))
            return DeliveryResult(ok=True, channel="file", message_id=str(filepath))
        except Exception as e:
            logger.error("FileAdapter write failed: %s", e)
            return DeliveryResult(ok=False, channel="file", error=str(e))
