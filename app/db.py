from collections.abc import Generator

from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

engine: Engine | None = None
SessionLocal: sessionmaker[Session] | None = None


def init_engine() -> Engine:
    """Create the SQLAlchemy engine and session factory from settings."""
    raise NotImplementedError


def init_db() -> None:
    """Enable pgvector, create tables, and seed the student/company spaces."""
    raise NotImplementedError


def get_session() -> Generator[Session, None, None]:
    """Yield a database session for a request or service call."""
    raise NotImplementedError
