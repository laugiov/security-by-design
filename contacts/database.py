"""Database session and connection management."""

import os
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from contacts.models import Base

# Database URL from environment
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://skylink:password@localhost:5432/skylink")

# Create engine
# For production: set pool_pre_ping=True to handle stale connections
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,  # Verify connections before using from pool
    echo=False,  # Set to True for SQL query logging (dev only)
)

# Create session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def create_tables() -> None:
    """Create all tables defined in models.

    Note: In production, use Alembic migrations instead.
    This is useful for development and testing.
    """
    Base.metadata.create_all(bind=engine)


def drop_tables() -> None:
    """Drop all tables defined in models.

    WARNING: This is destructive! Use only for testing.
    """
    Base.metadata.drop_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Get database session.

    Yields:
        SQLAlchemy Session instance

    Usage:
        ```python
        from fastapi import Depends
        from contacts.database import get_db

        @app.get("/example")
        def example(db: Session = Depends(get_db)):
            # Use db session here
            pass
        ```
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Test database utilities
_test_engine = None
_test_session_factory = None


def get_test_db() -> Session:
    """Get test database session (SQLite in-memory).

    Returns:
        SQLAlchemy Session for testing

    Usage in tests:
        ```python
        from contacts.database import get_test_db

        def test_example():
            db = get_test_db()
            # Use db for testing
            db.close()
        ```
    """
    global _test_engine, _test_session_factory

    if _test_engine is None:
        # Use SQLite in-memory for tests
        _test_engine = create_engine(
            "sqlite:///:memory:",
            echo=False,
            connect_args={"check_same_thread": False},  # Required for SQLite
        )
        Base.metadata.create_all(bind=_test_engine)
        _test_session_factory = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=_test_engine,
        )

    return _test_session_factory()


def reset_test_db() -> None:
    """Reset test database (drop and recreate all tables).

    Useful to ensure test isolation.
    """
    global _test_engine

    if _test_engine is not None:
        Base.metadata.drop_all(bind=_test_engine)
        Base.metadata.create_all(bind=_test_engine)
