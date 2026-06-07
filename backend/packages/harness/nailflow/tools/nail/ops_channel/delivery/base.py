# ops_channel/delivery/base.py
"""Delivery 基座：ChannelCapability / DeliveryTarget / AbstractChannelAdapter / DeliveryResult。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Flag, auto
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .messages.base import AbstractMessage


class ChannelCapability(Flag):
    TEXT = auto()
    CARD = auto()
    BUTTON = auto()
    TEMPLATE = auto()
    MARKDOWN = auto()
    THREAD = auto()
    FILE = auto()
    MENTION = auto()


@dataclass
class DeliveryTarget:
    channel: str
    recipient: str
    thread_id: str | None = None
    account_id: str | None = None


@dataclass
class DeliveryResult:
    ok: bool
    channel: str
    message_id: str = ""
    error: str = ""


class AbstractChannelAdapter(ABC):
    @property
    @abstractmethod
    def channel_id(self) -> str: ...

    @property
    @abstractmethod
    def capabilities(self) -> ChannelCapability: ...

    @abstractmethod
    async def send(self, target: DeliveryTarget, message: "AbstractMessage") -> DeliveryResult: ...

    async def health_check(self) -> bool:
        return True
