from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from .config import settings

if settings.is_production and settings.database_url.startswith("sqlite"):
    raise RuntimeError("SQLite is local-development only. Set DATABASE_URL to managed PostgreSQL in production.")

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine_options = {"pool_pre_ping": True, "connect_args": connect_args}
if not settings.database_url.startswith("sqlite"):
    engine_options.update({"pool_recycle": 300, "pool_size": 5, "max_overflow": 2})
engine = create_engine(settings.database_url, **engine_options)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


def get_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
