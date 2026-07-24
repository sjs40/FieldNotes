"""Explicit, operator-run Alembic migration command; never invoked by app startup."""
import os
import sys
from pathlib import Path
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine
from alembic.runtime.migration import MigrationContext
from backend.app.config import settings
from backend.app.database import database_url

def main() -> int:
    if settings.is_production and os.getenv("FIELDNOTES_CONFIRM_MIGRATIONS") != "yes":
        print("Refusing production migration. Set FIELDNOTES_CONFIRM_MIGRATIONS=yes after verifying DATABASE_URL.", file=sys.stderr)
        return 2
    config = Config(str(Path(__file__).parents[2] / "alembic.ini"))
    # Reuse the application's normalization for Supabase/Postgres URLs.
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    script = ScriptDirectory.from_config(config)
    engine = create_engine(database_url)
    with engine.connect() as connection:
        current = MigrationContext.configure(connection).get_current_revision()
    print(f"Current revision: {current or 'base'}\nTarget revision: {script.get_current_head()}")
    command.upgrade(config, "head")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
