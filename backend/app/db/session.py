from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from fastapi import Request
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

# The database is a network hop away (Supabase, another region: ~145ms per
# round trip), so the number of round trips per request *is* the latency.
# The defaults spent three on every request before the first real query:
#   - pool_pre_ping: a SELECT 1 on every checkout,
#   - psycopg2's BEGIN, sent on its own before the first statement,
#   - COMMIT at the end, even for a GET that changed nothing.
# So the base engine runs in autocommit (reads need no transaction) and keeps
# connections healthy with TCP keepalives and recycling instead of pinging.
# Anything that writes takes a real transaction -- see get_session_factory.
_POOL_RECYCLE_SECONDS = 300


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    if not settings.database_configured:
        raise RuntimeError(
            "DATABASE_URL is not set. Copy it from Supabase Dashboard -> "
            "Project Settings -> Database -> Connection string (URI)."
        )

    return create_engine(
        settings.database_url,
        isolation_level="AUTOCOMMIT",
        pool_pre_ping=False,
        pool_recycle=_POOL_RECYCLE_SECONDS,
        pool_size=5,
        max_overflow=5,
        connect_args={
            # Keep idle pooled connections alive through NATs and the pooler,
            # which is what pre-ping was protecting against.
            "keepalives": 1,
            "keepalives_idle": 30,
            "keepalives_interval": 10,
            "keepalives_count": 3,
        },
    )


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    """Transactional sessions: all-or-nothing, rollback works.

    Used by every request that can write, and by the scripts (seed, demo data,
    backfills), which rely on rollback.
    """
    transactional = get_engine().execution_options(isolation_level="READ COMMITTED")
    return sessionmaker(bind=transactional, autocommit=False, autoflush=False)


@lru_cache
def _read_session_factory() -> sessionmaker[Session]:
    """Autocommit sessions for GET requests: no BEGIN, no COMMIT."""
    return sessionmaker(bind=get_engine(), autocommit=False, autoflush=False)


@contextmanager
def read_session() -> Iterator[Session]:
    """A short-lived autocommit session, for reads fanned out to threads.

    Sees only committed data -- never use it for anything a write in the
    current request has to be visible to.
    """
    session = _read_session_factory()()
    try:
        yield session
    finally:
        session.close()


def get_db(request: Request) -> Iterator[Session]:
    """FastAPI dependency yielding a request-scoped session.

    GETs read in autocommit. The one write a GET can make (the throttled
    priority sweep on the ticket list) is per-row and safe to commit as it
    goes. POST/PATCH/DELETE get a real transaction.
    """
    reading = request.method in ("GET", "HEAD")
    factory = _read_session_factory() if reading else get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
