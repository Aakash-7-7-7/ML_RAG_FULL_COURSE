"""
Database engine and session management.

Provides a single SQLAlchemy engine + session factory used across the app,
plus a context-managed helper (`get_session`) so callers never leak
connections or forget to commit/rollback.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths / config
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_DIR = PROJECT_ROOT / "database"
DB_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DB_DIR / "agent_memory.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"

# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------
# check_same_thread=False is required because SQLite objects created in one
# thread cannot be used in another by default, and this app may call the DB
# from LangGraph nodes running off the main thread.

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    pool_pre_ping=True,
    future=True,
)


def _enable_sqlite_pragmas() -> None:
    """Enable foreign keys and WAL mode for better concurrency/integrity."""
    from sqlalchemy import event

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()


_enable_sqlite_pragmas()

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    future=True,
)


def init_db() -> None:
    """
    Create all tables that don't already exist.

    Call this once at application startup (e.g. in main.py) *after*
    importing database.models, so the metadata is populated.
    """
    from database import models  # local import avoids circular imports

    try:
        models.Base.metadata.create_all(bind=engine)
        logger.info("Database initialized at %s", DB_PATH)
    except SQLAlchemyError:
        logger.exception("Failed to initialize database")
        raise


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """
    Context-managed DB session.

    Usage:
        with get_session() as session:
            session.add(obj)
            # commit happens automatically on clean exit

    Commits on success, rolls back on any exception, and always closes.
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        logger.exception("Session rolled back due to an error")
        raise
    finally:
        session.close()