# ops_channel/delivery/messages/base.py
"""消息类型层次：通道无关的标准化消息表示。"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class MessageKind(Enum):
    TEXT = "text"
    CARD = "card"
    MARKDOWN = "markdown"
    TEMPLATE = "template"
    FILE = "file"


@dataclass
class AbstractMessage:
    kind: MessageKind

    def to_primitive(self) -> dict[str, Any]:
        raise NotImplementedError


@dataclass
class TextMessage(AbstractMessage):
    content: str

    def __init__(self, content: str):
        self.kind = MessageKind.TEXT
        self.content = content

    def to_primitive(self) -> dict[str, Any]:
        return {"kind": "text", "content": self.content}


@dataclass
class MarkdownMessage(AbstractMessage):
    content: str

    def __init__(self, content: str):
        self.kind = MessageKind.MARKDOWN
        self.content = content

    def to_primitive(self) -> dict[str, Any]:
        return {"kind": "markdown", "content": self.content}


@dataclass
class CardMessage(AbstractMessage):
    """交互式卡片消息：header + sections + buttons。"""
    header_title: str
    header_color: str = "blue"
    sections: list["CardSection"] = field(default_factory=list)
    buttons: list["CardButton"] = field(default_factory=list)

    def __init__(
        self,
        header_title: str,
        header_color: str = "blue",
        sections: list["CardSection"] | None = None,
        buttons: list["CardButton"] | None = None,
    ):
        self.kind = MessageKind.CARD
        self.header_title = header_title
        self.header_color = header_color
        self.sections = sections or []
        self.buttons = buttons or []

    def to_primitive(self) -> dict[str, Any]:
        return {
            "kind": "card",
            "header": {"title": self.header_title, "color": self.header_color},
            "sections": [s.to_primitive() for s in self.sections],
            "buttons": [b.to_primitive() for b in self.buttons],
        }


@dataclass
class FileMessage(AbstractMessage):
    """文件消息：字节内容 + 文件名 + MIME 类型。"""
    content: bytes
    filename: str
    mime_type: str = "application/pdf"

    def __init__(self, content: bytes, filename: str, mime_type: str = "application/pdf"):
        self.kind = MessageKind.FILE  # type: ignore[call-arg]
        self.content = content
        self.filename = filename
        self.mime_type = mime_type

    def to_primitive(self) -> dict[str, Any]:
        return {
            "kind": "file",
            "filename": self.filename,
            "mime_type": self.mime_type,
            "size": len(self.content),
        }
