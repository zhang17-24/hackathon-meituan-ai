# ops_channel/delivery/registry.py
"""适配器注册中心：配置驱动加载 + 能力查询。"""
from __future__ import annotations

import importlib
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base import AbstractChannelAdapter, ChannelCapability

logger = logging.getLogger(__name__)


class AdapterRegistry:
    def __init__(self):
        self._adapters: dict[str, "AbstractChannelAdapter"] = {}

    def register(self, adapter: "AbstractChannelAdapter") -> None:
        self._adapters[adapter.channel_id] = adapter
        logger.info("Registered channel adapter: %s", adapter.channel_id)

    def get(self, channel_id: str) -> "AbstractChannelAdapter | None":
        return self._adapters.get(channel_id)

    def list_all(self) -> list[str]:
        return list(self._adapters.keys())

    def list_capable(self, capability: "ChannelCapability") -> list[str]:
        result = []
        for cid, ad in self._adapters.items():
            if capability in ad.capabilities:
                result.append(cid)
        return result

    def load_from_config(self, channels_config: dict) -> None:
        for channel_id, cfg in channels_config.items():
            if not cfg.get("enabled", True):
                logger.info("Channel %s disabled, skipping", channel_id)
                continue
            adapter_path = cfg.get("adapter", "")
            if not adapter_path:
                continue
            try:
                module_path, class_name = adapter_path.split(":")
                # resolve relative path to absolute
                if module_path.startswith("ops_channel."):
                    module_path = "packages.harness.nailflow.tools.nail." + module_path
                mod = importlib.import_module(module_path)
                adapter_cls = getattr(mod, class_name)
                adapter = adapter_cls(config=cfg.get("config", {}))
                self.register(adapter)
            except Exception:
                logger.exception("Failed to load adapter for channel %s", channel_id)
