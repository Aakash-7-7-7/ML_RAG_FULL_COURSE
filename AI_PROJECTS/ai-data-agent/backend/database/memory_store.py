"""
CRUD operations for structured memory (curated key/value facts).

This is the "important stuff" layer — deduplicated facts the Memory
Manager decides are worth keeping long-term, as opposed to the raw
message log handled by message_store.py.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.dialects.sqlite import insert as sqlite_upsert

from database.db import get_session
from database.models import StructuredMemory

logger = logging.getLogger(__name__)


class MemoryStoreError(RuntimeError):
    """Raised when a memory_store operation fails unexpectedly."""


def upsert_memory(conversation_id: str, key: str, value: str) -> str:
    """
    Insert a new memory fact or update it if (conversation_id, key) already
    exists. Returns the memory row id.

    Uses SQLite's native ON CONFLICT upsert so this is a single atomic
    statement rather than a select-then-insert-or-update race.
    """
    if not key or not key.strip():
        raise ValueError("Memory key cannot be empty")

    try:
        with get_session() as session:
            stmt = sqlite_upsert(StructuredMemory).values(
                conversation_id=conversation_id,
                key=key,
                value=value,
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["conversation_id", "key"],
                set_={"value": value},
            )
            session.execute(stmt)

            row = session.execute(
                select(StructuredMemory).where(
                    StructuredMemory.conversation_id == conversation_id,
                    StructuredMemory.key == key,
                )
            ).scalar_one()
            return row.id
    except SQLAlchemyError as exc:
        logger.exception(
            "Failed to upsert memory key=%s for conversation %s", key, conversation_id
        )
        raise MemoryStoreError("Could not save memory fact") from exc


def get_structured_memory(conversation_id: str) -> dict[str, Any]:
    """Return all structured memory for a conversation as a flat {key: value} dict."""
    try:
        with get_session() as session:
            rows = session.execute(
                select(StructuredMemory).where(
                    StructuredMemory.conversation_id == conversation_id
                )
            ).scalars().all()
            return {row.key: row.value for row in rows}
    except SQLAlchemyError as exc:
        logger.exception("Failed to fetch structured memory for conversation %s", conversation_id)
        raise MemoryStoreError("Could not fetch structured memory") from exc


def delete_memory_key(conversation_id: str, key: str) -> bool:
    """Delete a single memory fact. Returns True if a row was deleted."""
    try:
        with get_session() as session:
            row = session.execute(
                select(StructuredMemory).where(
                    StructuredMemory.conversation_id == conversation_id,
                    StructuredMemory.key == key,
                )
            ).scalar_one_or_none()
            if row is None:
                return False
            session.delete(row)
            return True
    except SQLAlchemyError as exc:
        logger.exception(
            "Failed to delete memory key=%s for conversation %s", key, conversation_id
        )
        raise MemoryStoreError("Could not delete memory fact") from exc