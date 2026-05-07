"""Database engine and session factory for LoreForge.

Creates a SQLite database at app_data/loreforge.db (beside the app_data/
directory that already holds preferences.json).  Uses SQLAlchemy 2.x.

Public API
----------
engine        — bound SQLAlchemy engine (sqlite)
SessionLocal  — session factory (call SessionLocal() to get a Session)
init_db()     — create all tables defined in core.models (idempotent)
"""
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# ── Paths ──────────────────────────────────────────────────────────────────────
# core/db.py lives in core/, so .parent.parent goes to the project root.
_APP_DATA_DIR = Path(__file__).resolve().parent.parent / "app_data"
_APP_DATA_DIR.mkdir(exist_ok=True)

_DB_PATH = _APP_DATA_DIR / "loreforge.db"
_DB_URL = f"sqlite:///{_DB_PATH}"

# ── Engine ─────────────────────────────────────────────────────────────────────
# check_same_thread=False is required for Streamlit, which may call SQLAlchemy
# from multiple threads within a single session.
engine = create_engine(
    _DB_URL,
    connect_args={"check_same_thread": False},
    echo=False,
)

# ── Session factory ────────────────────────────────────────────────────────────
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


# ── Table creation ─────────────────────────────────────────────────────────────
def init_db() -> None:
    """Create all SQLAlchemy-mapped tables if they do not already exist.

    Safe to call repeatedly — uses CREATE TABLE IF NOT EXISTS semantics via
    SQLAlchemy's metadata.create_all().  Import core.models before calling so
    that all mapped classes are registered with Base.metadata.
    """
    from core.models import Base  # local import avoids circular dependency
    Base.metadata.create_all(bind=engine)
