"""
Context Builder — assembles what gets sent to the LLM/agent.

Combines three sources, matching the architecture diagram:
    1. Recent messages       (database.message_store)
    2. Structured memory     (database.memory_store)
    3. Current dataset state (passed in by the caller, e.g. csv_handler)

This module is read-only with respect to storage: it never writes to the
database. Writing happens after the LLM responds, in memory_manager.py.
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

from database.message_store import get_recent_messages
from database.memory_store import get_structured_memory

logger = logging.getLogger(__name__)

DEFAULT_RECENT_MESSAGE_LIMIT = 20

_ROLE_TO_MESSAGE_CLASS: dict[str, type[BaseMessage]] = {
    "user": HumanMessage,
    "assistant": AIMessage,
    "system": SystemMessage,
    "tool": ToolMessage,
}


def _format_structured_memory(memory: dict[str, Any]) -> str:
    """Render structured memory facts as a compact block for a system message."""
    if not memory:
        return ""
    lines = [f"- {key}: {value}" for key, value in memory.items()]
    return "Known facts about this user/conversation:\n" + "\n".join(lines)


def _rows_to_langchain_messages(rows: list[dict[str, Any]]) -> list[BaseMessage]:
    """Convert stored message dicts back into LangChain message objects."""
    messages: list[BaseMessage] = []
    for row in rows:
        role = row.get("role", "user")
        message_cls = _ROLE_TO_MESSAGE_CLASS.get(role)
        if message_cls is None:
            logger.warning("Unknown message role '%s' skipped in context build", role)
            continue
        messages.append(message_cls(content=row["content"]))
    return messages


def build_context(
    conversation_id: str,
    dataset_context: dict[str, Any] | None = None,
    recent_limit: int = DEFAULT_RECENT_MESSAGE_LIMIT,
) -> dict[str, Any]:
    """
    Build the full context payload for a single agent turn.

    Returns a dict with:
        messages          - list[BaseMessage], ready to pass to the LLM/graph
        structured_memory - dict of curated facts
        dataset_state     - whatever the caller passed in (or {})

    Raises no exceptions on empty history/memory — a brand-new conversation
    with nothing stored yet is a normal, expected case.
    """
    dataset_context = dataset_context or {}

    recent_rows = get_recent_messages(conversation_id, limit=recent_limit)
    structured_memory = get_structured_memory(conversation_id)

    messages: list[BaseMessage] = []

    memory_summary = _format_structured_memory(structured_memory)
    if memory_summary:
        messages.append(SystemMessage(content=memory_summary))

    messages.extend(_rows_to_langchain_messages(recent_rows))

    return {
        "messages": messages,
        "structured_memory": structured_memory,
        "dataset_state": dataset_context,
    }