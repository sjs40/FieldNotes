from logging.config import fileConfig
from alembic import context
from sqlalchemy import engine_from_config, pool
from backend.app.database import Base, database_url
import backend.app.models  # noqa: F401 - registers metadata

config = context.config
# ConfigParser treats percent signs as interpolation markers. Supabase URLs
# correctly percent-encode password characters, so escape only for Alembic's
# config layer; SQLAlchemy receives the original value when it is read back.
config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
if config.config_file_name:
    fileConfig(config.config_file_name)
target_metadata = Base.metadata


def run_migrations_offline():
    context.configure(url=database_url, target_metadata=target_metadata, literal_binds=True, compare_type=True)
    with context.begin_transaction(): context.run_migrations()


def run_migrations_online():
    connectable = engine_from_config(config.get_section(config.config_ini_section), prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction(): context.run_migrations()


if context.is_offline_mode(): run_migrations_offline()
else: run_migrations_online()
