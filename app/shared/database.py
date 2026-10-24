"""
Database connection shared by every module.

    get_db()   FastAPI dependency that gives a route one database session
    init_db()  creates any missing tables (called once when the app starts)
"""
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.shared.config.settings import get_settings


@lru_cache
def get_engine() -> Engine:
    url = get_settings().database_url
    # SQLite (used only in quick tests) needs this flag to work with FastAPI.
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, connect_args=connect_args, pool_pre_ping=True)


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


def get_db():
    """Open a session for one request and always close it afterwards."""
    db = get_session_factory()()
    try:
        yield db
    finally:
        db.close()


def init_db(engine: Engine | None = None) -> None:
    """Create all tables that do not exist yet. Existing tables are left alone."""
    from app.shared import models  # importing registers every model on Base

    models.Base.metadata.create_all(bind=engine or get_engine())
