"""SQLite engine and session factory for LoreForge metadata."""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.storage import APP_DATA_DIR, ensure_app_directories

# ── Paths ──────────────────────────────────────────────────────────────────────
ensure_app_directories()

_DB_PATH = APP_DATA_DIR / "loreforge.db"
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
    """Create all SQLAlchemy-mapped tables if they do not already exist."""
    from core.models import Base  # local import avoids circular dependency
    Base.metadata.create_all(bind=engine)
