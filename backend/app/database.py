from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from .config import settings

database_url = settings.database_url
if database_url.startswith("postgres://"):
    database_url = "postgresql+psycopg://" + database_url.removeprefix("postgres://")
elif database_url.startswith("postgresql://") and "+" not in database_url.split("://", 1)[0]:
    database_url = "postgresql+psycopg://" + database_url.removeprefix("postgresql://")
if settings.is_production and database_url.startswith("sqlite"):
    raise RuntimeError("SQLite is local-development only. Set DATABASE_URL to managed PostgreSQL in production.")

connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
engine_options = {"pool_pre_ping": True, "connect_args": connect_args}
if not database_url.startswith("sqlite"):
    engine_options.update({"pool_recycle": 300, "pool_size": 5, "max_overflow": 2})
engine = create_engine(database_url, **engine_options)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


def get_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
