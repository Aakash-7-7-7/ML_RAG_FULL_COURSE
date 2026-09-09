"""
api.py — FastAPI layer exposing the AI data agent over HTTP.

Endpoints:
    GET  /health                              - liveness/readiness check
    POST /api/datasets/upload                 - upload a CSV, becomes the active dataset
    GET  /api/datasets/overview               - summary of the active dataset
    POST /api/conversations                   - create a new conversation, returns its id
    GET  /api/conversations/{id}/messages     - raw chat history for a conversation
    GET  /api/conversations/{id}/memory       - structured memory for a conversation
    POST /api/chat                            - send a message, get the agent's reply
    GET  /api/charts/{chart_id}               - fetch a generated chart PNG

Run with:
    uvicorn api:app --reload --port 8000

IMPORTANT — current design limitation: csv_handler.py holds ONE global
dataframe for the whole process, not one per conversation/user. That's
fine for a single-user local tool, but if this API will ever serve more
than one user at a time, the dataset needs to become per-conversation
(e.g. keyed in a dict by conversation_id) before that's safe. Flagging
this now so it doesn't surprise you later.
"""

from __future__ import annotations

import ast
import base64
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
import re

from fastapi import FastAPI, HTTPException, UploadFile, File, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

from database.db import init_db
from database.message_store import (
    create_conversation,
    get_or_create_conversation,
    get_recent_messages,
    MessageStoreError,
)
from database.memory_store import get_structured_memory, MemoryStoreError
from memory.context_builder import build_context
from memory.memory_manager import update_memory

from csv_handler import load_csv_to_dataframe, set_current_dataframe, get_current_dataframe
from tools import CHARTS_DIR
from agent import app as agent_graph

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("api")

UPLOAD_DIR = Path(__file__).resolve().parent / "data" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    logger.info("Database initialized.")
    yield
    logger.info("Shutting down.")


app = FastAPI(
    title="AI Data Agent API",
    version="1.0.0",
    lifespan=lifespan,
)

# Loosen this for local dev with an Electron/React frontend. Lock it down
# to your actual frontend origin(s) before shipping anywhere real.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ConversationCreateResponse(BaseModel):
    conversation_id: str


class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    metadata: dict[str, Any] | None = None
    created_at: str


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="The user's message to the agent.")
    conversation_id: str | None = Field(
        None, description="Existing conversation id. Omit to start a new conversation."
    )


class ChatResponse(BaseModel):
    conversation_id: str
    response: str
    chart_id: str | None = None
    chart_url: str | None = None
    chart_base64: str | None = Field(
        None,
        description=(
            "Data URI (data:image/png;base64,...) of the generated chart, "
            "ready to drop straight into an <img src> with no extra request. "
            "chart_url is still provided as a fallback / for sharing a link."
        ),
    )
    promoted_memory: dict[str, str] = Field(default_factory=dict)


class DatasetOverviewResponse(BaseModel):
    filename: str | None = None
    total_rows: int | None = None
    total_columns: int | None = None
    column_names: list[str] | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_last_ai_text(messages: list) -> str:
    for message in reversed(messages):
        if isinstance(message, AIMessage) and message.content:
            return message.content
    return "The agent did not return a text response."


def _extract_chart_info(messages: list) -> dict[str, str] | None:
    """
    Extract chart information from the LangGraph result.

    Supports:
    1. ToolMessage containing a Python dict/string dict
    2. AIMessage containing chart_id
    3. AIMessage containing a chart PNG file path
    """

    # -------------------------------------------------
    # FIRST: Look through ToolMessages
    # -------------------------------------------------

    for message in reversed(messages):

        if not isinstance(message, ToolMessage):
            continue

        content = message.content

        if isinstance(content, dict):

            parsed = content

        elif isinstance(content, str):

            try:

                parsed = ast.literal_eval(content)

            except (ValueError, SyntaxError):

                continue

        else:

            continue


        if (
            isinstance(parsed, dict)
            and parsed.get("chart_id")
        ):

            return {

                "chart_id":
                    str(parsed["chart_id"]),

                "file_path":
                    str(
                        parsed.get(
                            "file_path",
                            ""
                        )
                    )
            }


    # -------------------------------------------------
    # SECOND: Look for chart_id or PNG path
    # inside any AI message
    # -------------------------------------------------

    for message in reversed(messages):

        if not isinstance(
            message,
            AIMessage
        ):
            continue


        content = str(
            message.content
        )


        # ---------------------------------------------
        # Look for:
        #
        # "chart_id": "abc-123"
        # or
        # 'chart_id': 'abc-123'
        # ---------------------------------------------

        chart_id_match = re.search(

            r"""
            chart_id
            ["']?\s*[:=]\s*
            ["']?
            ([A-Za-z0-9_-]+)
            """,

            content,

            re.IGNORECASE |
            re.VERBOSE

        )


        if chart_id_match:

            chart_id = (
                chart_id_match
                .group(1)
            )


            return {

                "chart_id":
                    chart_id,

                "file_path":
                    ""

            }


        # ---------------------------------------------
        # Look for:
        #
        # something.png
        #
        # Example:
        #
        # C:\...\charts\
        # 6435f311-7290-439c-88e6-17760e381653.png
        # ---------------------------------------------

        png_match = re.search(

            r"""
            ([A-Za-z0-9_-]+)
            \.png
            """,

            content,

            re.IGNORECASE |
            re.VERBOSE

        )


        if png_match:

            chart_id = (
                png_match
                .group(1)
            )


            return {

                "chart_id":
                    chart_id,

                "file_path":
                    ""

            }


    return None


def _encode_chart_as_data_uri(chart_id: str) -> str | None:
    """
    Read the freshly saved chart PNG and return it as a base64 data URI.

    Returns None (rather than raising) if the file is missing or unreadable
    so a chart-encoding hiccup never turns a successful chat reply into a
    500 error — the caller still gets chart_url as a fallback.
    """
    file_path = CHARTS_DIR / f"{chart_id}.png"
    try:
        image_bytes = file_path.read_bytes()
    except OSError:
        logger.exception("Could not read chart file for inline encoding: %s", file_path)
        return None

    encoded = base64.b64encode(image_bytes).decode("ascii")
    return f"data:image/png;base64,{encoded}"


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Datasets
# ---------------------------------------------------------------------------

@app.post("/api/datasets/upload", response_model=DatasetOverviewResponse, tags=["datasets"])
async def upload_dataset(file: UploadFile = File(...)) -> DatasetOverviewResponse:
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only .csv files are supported.")

    dest_path = UPLOAD_DIR / file.filename
    try:
        contents = await file.read()
        dest_path.write_bytes(contents)
    except Exception:
        logger.exception("Failed to save uploaded file %s", file.filename)
        raise HTTPException(status_code=500, detail="Could not save the uploaded file.")

    try:
        df = load_csv_to_dataframe(str(dest_path))
        set_current_dataframe(df)
    except Exception:
        logger.exception("Failed to parse CSV %s", file.filename)
        raise HTTPException(status_code=400, detail="Could not parse the uploaded CSV.")

    rows, cols = df.shape
    logger.info("Dataset loaded via upload: %s (%d rows, %d cols)", file.filename, rows, cols)

    return DatasetOverviewResponse(
        filename=file.filename,
        total_rows=rows,
        total_columns=cols,
        column_names=list(df.columns),
    )


@app.get("/api/datasets/overview", response_model=DatasetOverviewResponse, tags=["datasets"])
def dataset_overview() -> DatasetOverviewResponse:
    df = get_current_dataframe()
    if df is None or df.empty:
        raise HTTPException(status_code=404, detail="No dataset loaded yet. Upload one first.")

    rows, cols = df.shape
    return DatasetOverviewResponse(
        filename=None,
        total_rows=rows,
        total_columns=cols,
        column_names=list(df.columns),
    )


# ---------------------------------------------------------------------------
# Conversations
# ---------------------------------------------------------------------------

@app.post(
    "/api/conversations",
    response_model=ConversationCreateResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["conversations"],
)
def create_new_conversation() -> ConversationCreateResponse:
    try:
        conversation_id = create_conversation()
        return ConversationCreateResponse(conversation_id=conversation_id)
    except MessageStoreError:
        raise HTTPException(status_code=500, detail="Could not create a new conversation.")


@app.get(
    "/api/conversations/{conversation_id}/messages",
    response_model=list[MessageOut],
    tags=["conversations"],
)
def list_messages(conversation_id: str, limit: int = 50) -> list[MessageOut]:
    try:
        rows = get_recent_messages(conversation_id, limit=limit)
        return [MessageOut(**row) for row in rows]
    except MessageStoreError:
        raise HTTPException(status_code=500, detail="Could not fetch messages.")


@app.get("/api/conversations/{conversation_id}/memory", tags=["conversations"])
def get_memory(conversation_id: str) -> dict[str, str]:
    try:
        return get_structured_memory(conversation_id)
    except MemoryStoreError:
        raise HTTPException(status_code=500, detail="Could not fetch structured memory.")


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------

@app.post("/api/chat", response_model=ChatResponse, tags=["chat"])
def chat(request: ChatRequest) -> ChatResponse:
    conversation_id = get_or_create_conversation(request.conversation_id)

    dataset_context = {"dataset_loaded": get_current_dataframe() is not None}
    context = build_context(conversation_id, dataset_context=dataset_context)

    # NOTE: adjust these two state keys if your actual state.py's State
    # TypedDict uses different field names than test_agent.py implies.
    graph_input = {
        "messages": context["messages"] + [HumanMessage(content=request.message)],
        "dataset_context": context["dataset_state"],
    }

    try:
        result = agent_graph.invoke(graph_input)
    except Exception:
        logger.exception("Agent invocation failed for conversation %s", conversation_id)
        raise HTTPException(status_code=502, detail="The agent failed to produce a response.")

    result_messages = result["messages"]
    assistant_text = _extract_last_ai_text(result_messages)
    chart_info = _extract_chart_info(result_messages)

    chart_id = chart_info["chart_id"] if chart_info else None
    chart_base64 = _encode_chart_as_data_uri(chart_id) if chart_id else None

    try:
        promoted = update_memory(conversation_id, request.message, assistant_text)
    except Exception:
        logger.exception("Failed to persist turn for conversation %s", conversation_id)
        promoted = {}

    return ChatResponse(
        conversation_id=conversation_id,
        response=assistant_text,
        chart_id=chart_id,
        chart_url=f"/api/charts/{chart_id}" if chart_id else None,
        chart_base64=chart_base64,
        promoted_memory=promoted,
    )


# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------

@app.get("/api/charts/{chart_id}", tags=["charts"])
def get_chart(chart_id: str) -> FileResponse:
    # Reject anything that isn't a bare filename component to prevent path traversal
    # (e.g. "../../etc/passwd") before it ever touches the filesystem.
    if "/" in chart_id or "\\" in chart_id or ".." in chart_id:
        raise HTTPException(status_code=400, detail="Invalid chart id.")

    file_path = CHARTS_DIR / f"{chart_id}.png"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Chart not found.")

    return FileResponse(file_path, media_type="image/png")