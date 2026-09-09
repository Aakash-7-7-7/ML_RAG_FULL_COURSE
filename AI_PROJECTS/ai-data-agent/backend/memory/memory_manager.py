"""
Memory Manager — runs after the LLM/agent responds.

Responsibilities (matching the bottom half of the architecture diagram):
    1. Persist the new user + assistant turn as raw messages.
    2. Decide whether anything in the turn is worth promoting into
       structured (long-term) memory, and upsert it if so.

Fact extraction uses a small, cheap LLM call with a strict JSON-only
prompt. If that call fails or returns garbage, the turn is still saved —
extraction failures should never block persistence of the conversation.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from database.message_store import save_message
from database.memory_store import upsert_memory
from llm import connect_llm

logger = logging.getLogger(__name__)

_EXTRACTION_SYSTEM_PROMPT = """You extract durable facts worth remembering about a user \
from a single conversation turn in a data-analysis assistant.

Only extract facts that are STABLE and USEFUL across future turns, such as:
- stated preferences (e.g. preferred chart type, color scheme)
- the dataset currently being worked on
- the user's overall analysis goal

Do NOT extract one-off questions, transient values, or anything already obvious \
from the raw message text.

Respond ONLY with a JSON object mapping short snake_case keys to string values. \
If there is nothing worth remembering, respond with exactly: {}
Do not include markdown fences, prose, or explanation — JSON only."""


def _extract_facts(user_text: str, assistant_text: str) -> dict[str, str]:
    """
    Ask the LLM to pull durable facts out of a turn.

    Returns {} on any failure (bad JSON, empty response, LLM error) rather
    than raising, since fact extraction is a nice-to-have, not critical path.
    """
    try:
        llm = connect_llm()
        prompt = (
            f"{_EXTRACTION_SYSTEM_PROMPT}\n\n"
            f"User message: {user_text}\n"
            f"Assistant response: {assistant_text}\n\n"
            f"JSON:"
        )
        response = llm.invoke(prompt)
        raw = (response.content or "").strip()

        # Defensively strip markdown fences if the model adds them anyway.
        if raw.startswith("```"):
            raw = raw.strip("`")
            raw = raw.split("\n", 1)[-1] if "\n" in raw else raw
            raw = raw.rsplit("```", 1)[0] if "```" in raw else raw
            raw = raw.strip()
            if raw.lower().startswith("json"):
                raw = raw[4:].strip()

        if not raw:
            return {}

        facts = json.loads(raw)
        if not isinstance(facts, dict):
            logger.warning("Fact extraction returned non-dict JSON, ignoring")
            return {}

        return {str(k): str(v) for k, v in facts.items() if v not in (None, "")}

    except (json.JSONDecodeError, ValueError):
        logger.warning("Fact extraction returned invalid JSON, skipping this turn")
        return {}
    except Exception:
        logger.exception("Fact extraction failed unexpectedly, skipping this turn")
        return {}


def update_memory(
    conversation_id: str,
    user_text: str,
    assistant_text: str,
    user_metadata: dict[str, Any] | None = None,
    assistant_metadata: dict[str, Any] | None = None,
    extract_facts: bool = True,
) -> dict[str, str]:
    """
    Persist a completed turn and (optionally) update structured memory.

    Returns the dict of facts that were promoted to structured memory
    (empty dict if none were found or extraction was skipped).
    """
    save_message(conversation_id, "user", user_text, metadata=user_metadata)
    save_message(conversation_id, "assistant", assistant_text, metadata=assistant_metadata)

    if not extract_facts:
        return {}

    facts = _extract_facts(user_text, assistant_text)

    for key, value in facts.items():
        try:
            upsert_memory(conversation_id, key, value)
        except Exception:
            logger.exception("Failed to upsert memory fact key=%s", key)

    if facts:
        logger.info("Promoted %d fact(s) to structured memory: %s", len(facts), list(facts))

    return facts