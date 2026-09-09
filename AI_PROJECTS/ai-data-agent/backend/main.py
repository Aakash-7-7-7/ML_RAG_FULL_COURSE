"""
main.py — manual test harness for the AI data agent.

Run this to sanity-check that three subsystems are wired together correctly:
    1. Data layer      -> CSV loads into csv_handler's current dataframe
    2. Agent layer      -> LangGraph app (agent.py) responds using tools.py
    3. Memory layer     -> messages + structured facts persist across turns
       in database/ and get rebuilt by memory/context_builder.py

Usage:
    python main.py                          # uses default CSV path below
    python main.py --csv path/to/file.csv
    python main.py --conversation-id <id>   # resume an existing conversation

Type 'exit' or 'quit' to stop. Type 'memory' at any prompt to print the
current structured memory for this conversation (useful for verifying the
memory layer without guessing from agent output alone).
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from langchain_core.messages import HumanMessage, AIMessage

from database.db import init_db
from database.message_store import get_or_create_conversation
from database.memory_store import get_structured_memory
from memory.context_builder import build_context
from memory.memory_manager import update_memory

from csv_handler import load_csv_to_dataframe, set_current_dataframe, get_current_dataframe
from agent import app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("main")

DEFAULT_CSV_PATH = "data/uploads/cars.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manual test harness for the AI data agent.")
    parser.add_argument(
        "--csv",
        type=str,
        default=DEFAULT_CSV_PATH,
        help=f"Path to the CSV to load (default: {DEFAULT_CSV_PATH})",
    )
    parser.add_argument(
        "--conversation-id",
        type=str,
        default=None,
        help="Resume an existing conversation instead of starting a new one.",
    )
    return parser.parse_args()


def check_llm_connection() -> bool:
    """Fail fast with a clear message if the LLM isn't reachable, instead of erroring mid-chat."""
    try:
        from llm import connect_llm

        llm = connect_llm()
        llm.invoke("ping")
        logger.info("LLM connection OK.")
        return True
    except Exception:
        logger.exception("LLM connection failed. Check LLM_URL / LLM_MODEL_NAME in your .env")
        return False


def load_dataset(csv_path: str) -> bool:
    """Load the CSV into csv_handler's global dataframe. Returns True on success."""
    path = Path(csv_path)
    if not path.exists():
        logger.error("CSV not found at %s", path.resolve())
        return False

    try:
        df = load_csv_to_dataframe(str(path))
        set_current_dataframe(df)
        rows, cols = df.shape
        logger.info("Loaded dataset: %s (%d rows, %d columns)", path.name, rows, cols)
        logger.info("Columns: %s", list(df.columns))
        return True
    except Exception:
        logger.exception("Failed to load CSV at %s", path)
        return False


def extract_last_ai_text(messages: list) -> str:
    """Pull the final AI-authored text out of a graph invocation's message list."""
    for message in reversed(messages):
        if isinstance(message, AIMessage) and message.content:
            return message.content
    return "(agent produced no text response — check tool output above)"


def print_memory_snapshot(conversation_id: str) -> None:
    memory = get_structured_memory(conversation_id)
    if not memory:
        print("[structured memory is currently empty]")
        return
    print("[structured memory]")
    for key, value in memory.items():
        print(f"  - {key}: {value}")


def run_repl(conversation_id: str) -> None:
    print(f"\nConversation ID: {conversation_id}")
    print("Type a question about your dataset. Type 'memory' to inspect stored facts, "
          "'exit' to quit.\n")

    while True:
        try:
            user_text = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break

        if not user_text:
            continue

        if user_text.lower() in {"exit", "quit"}:
            print("Exiting.")
            break

        if user_text.lower() == "memory":
            print_memory_snapshot(conversation_id)
            continue

        # 1. Rebuild context from storage (recent messages + structured memory)
        dataset_context = {"dataset_loaded": get_current_dataframe() is not None}
        context = build_context(conversation_id, dataset_context=dataset_context)

        # NOTE: adjust these two state keys if your actual state.py's State
        # TypedDict uses different field names than test_agent.py implies.
        graph_input = {
            "messages": context["messages"] + [HumanMessage(content=user_text)],
            "dataset_context": context["dataset_state"],
        }

        # 2. Run the agent graph
        try:
            result = app.invoke(graph_input)
        except Exception:
            logger.exception("Agent invocation failed")
            print("Agent: (error — see log above)")
            continue

        assistant_text = extract_last_ai_text(result["messages"])
        print(f"Agent: {assistant_text}")

        # 3. Persist the turn and let the memory manager promote any durable facts
        try:
            promoted = update_memory(conversation_id, user_text, assistant_text)
            if promoted:
                print(f"[memory updated: {list(promoted.keys())}]")
        except Exception:
            logger.exception("Failed to update memory for this turn")


def main() -> int:
    args = parse_args()

    print("=== AI Data Agent — startup checks ===")

    init_db()
    logger.info("Database initialized.")

    if not check_llm_connection():
        print("\nAborting: fix the LLM connection before continuing.")
        return 1

    if not load_dataset(args.csv):
        print("\nAborting: fix the CSV path before continuing.")
        return 1

    conversation_id = get_or_create_conversation(args.conversation_id)

    print("=== All systems ready ===\n")
    run_repl(conversation_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())