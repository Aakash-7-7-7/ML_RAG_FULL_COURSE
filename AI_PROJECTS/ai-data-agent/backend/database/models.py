"""
ORM models for conversation storage and structured memory.

Tables:
    Conversation      - one row per chat session
    Message           - raw turn-by-turn chat history (the "recent messages" layer)
    StructuredMemory  - curated key/value facts extracted from the conversation
                        (the "structured memory" layer in the architecture diagram)
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    String,
    Text,
    DateTime,
    ForeignKey,
    Enum, 
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)


class Base(DeclarativeBase):
    pass


def _uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MessageRole(str, enum.Enum):
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"
    SYSTEM = "system"


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )
    memories: Mapped[list["StructuredMemory"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Conversation id={self.id} title={self.title!r}>"


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        Index("ix_messages_conversation_created", "conversation_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    conversation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[MessageRole] = mapped_column(Enum(MessageRole), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Optional metadata: tool name, chart_id, token counts, etc. Stored as
    # JSON text rather than a JSON column so this works identically on
    # SQLite and Postgres without extra dialect handling.
    extra_metadata: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")

    def __repr__(self) -> str:  # pragma: no cover
        preview = (self.content or "")[:40]
        return f"<Message id={self.id} role={self.role} content={preview!r}>"


class StructuredMemory(Base):
    """
    Curated, deduplicated facts about the conversation/user — the "important
    stuff" the Memory Manager decides to keep, as opposed to the raw
    message log. One (conversation_id, key) pair is unique so upserts are
    straightforward (e.g. key="preferred_chart_type", value="bar_chart").
    """

    __tablename__ = "structured_memory"
    __table_args__ = (
        UniqueConstraint("conversation_id", "key", name="uq_memory_conversation_key"),
        Index("ix_memory_conversation_id", "conversation_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    conversation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    key: Mapped[str] = mapped_column(String(128), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    conversation: Mapped["Conversation"] = relationship(back_populates="memories")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<StructuredMemory key={self.key!r} value={self.value[:40]!r}>"