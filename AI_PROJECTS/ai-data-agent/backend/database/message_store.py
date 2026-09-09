"""
CRUD operations for conversations and raw chat messages.

This module owns the "recent messages" layer of the memory architecture.
It never talks to the LLM or decides what's "important" — that's
memory/memory_manager.py's job. This module just persists and retrieves.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import select, delete
from sqlalchemy.exc import SQLAlchemyError

from database.db import get_session
from database.models import Conversation, Message, MessageRole

logger = logging.getLogger(__name__)


class MessageStoreError(RuntimeError):
    """Raised when a message_store operation fails unexpectedly."""


# ---------------------------------------------------------------------------
# Conversations
# ---------------------------------------------------------------------------

def create_conversation(title: str | None = None) -> str:
    """Create a new conversation and return its id."""
    try:
        with get_session() as session:
            conversation = Conversation(title=title)
            session.add(conversation)
            session.flush()  # populate defaults (id) before commit
            return conversation.id
    except SQLAlchemyError as exc:
        logger.exception("Failed to create conversation")
        raise MessageStoreError("Could not create conversation") from exc


def get_or_create_conversation(conversation_id: str | None, title: str | None = None) -> str:
    """
    Return conversation_id if it exists, otherwise create a new one.

    Pass None the first time you talk to a user/session and persist the
    returned id on your side (e.g. in the LangGraph state or a cookie).
    """
    if conversation_id is None:
        return create_conversation(title=title)

    try:
        with get_session() as session:
            exists = session.get(Conversation, conversation_id)
            if exists:
                return conversation_id
        return create_conversation(title=title)
    except SQLAlchemyError as exc:
        logger.exception("Failed to look up conversation %s", conversation_id)
        raise MessageStoreError("Could not look up conversation") from exc


def delete_conversation(conversation_id: str) -> bool:
    """Delete a conversation and cascade-delete its messages/memory. Returns True if deleted."""
    try:
        with get_session() as session:
            conversation = session.get(Conversation, conversation_id)
            if conversation is None:
                return False
            session.delete(conversation)
            return True
    except SQLAlchemyError as exc:
        logger.exception("Failed to delete conversation %s", conversation_id)
        raise MessageStoreError("Could not delete conversation") from exc


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------

def save_message(
    conversation_id: str,
    role: str | MessageRole,
    content: str,
    metadata: dict[str, Any] | None = None,
) -> str:
    """
    Persist a single message and return its id.

    `role` accepts either a MessageRole or a plain string ("user",
    "assistant", "tool", "system") for convenience when calling from
    LangChain message objects.
    """
    if not content or not content.strip():
        raise ValueError("Message content cannot be empty")

    if isinstance(role, str):
        try:
            role = MessageRole(role.lower())
        except ValueError as exc:
            raise ValueError(
                f"Invalid role '{role}'. Must be one of: "
                f"{[r.value for r in MessageRole]}"
            ) from exc

    try:
        with get_session() as session:
            message = Message(
                conversation_id=conversation_id,
                role=role,
                content=content,
                extra_metadata=json.dumps(metadata) if metadata else None,
            )
            session.add(message)
            session.flush()
            return message.id
    except SQLAlchemyError as exc:
        logger.exception("Failed to save message for conversation %s", conversation_id)
        raise MessageStoreError("Could not save message") from exc


def get_recent_messages(
    conversation_id: str,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """
    Return the most recent `limit` messages for a conversation, oldest first
    (ready to feed straight into an LLM context window).
    """
    try:
        with get_session() as session:
            stmt = (
                select(Message)
                .where(Message.conversation_id == conversation_id)
                .order_by(Message.created_at.desc())
                .limit(limit)
            )
            rows = session.execute(stmt).scalars().all()

            # rows come back newest-first; reverse for chronological order
            return [
                {
                    "id": m.id,
                    "role": m.role.value,
                    "content": m.content,
                    "metadata": json.loads(m.extra_metadata) if m.extra_metadata else None,
                    "created_at": m.created_at.isoformat(),
                }
                for m in reversed(rows)
            ]
    except SQLAlchemyError as exc:
        logger.exception("Failed to fetch messages for conversation %s", conversation_id)
        raise MessageStoreError("Could not fetch messages") from exc


def clear_messages(conversation_id: str) -> int:
    """Delete all messages for a conversation (keeps the conversation + memory rows). Returns count deleted."""
    try:
        with get_session() as session:
            stmt = delete(Message).where(Message.conversation_id == conversation_id)
            result = session.execute(stmt)
            return result.rowcount or 0
    except SQLAlchemyError as exc:
        logger.exception("Failed to clear messages for conversation %s", conversation_id)
        raise MessageStoreError("Could not clear messages") from exc