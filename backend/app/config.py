from pathlib import Path
import os
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = Field(default_factory=lambda: os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL") or f"sqlite:///{Path(__file__).parents[2] / 'fieldnotes.db'}")
    quote_cache_minutes: int = 15
    default_benchmark: str = "SPY"
    allow_yfinance: bool = True
    supabase_url: str | None = Field(default_factory=lambda: os.getenv("SUPABASE_URL") or os.getenv("NEXT_PUBLIC_SUPABASE_URL"))
    supabase_publishable_key: str | None = Field(default_factory=lambda: os.getenv("SUPABASE_PUBLISHABLE_KEY") or os.getenv("SUPABASE_ANON_KEY") or os.getenv("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY") or os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY"))

    @property
    def is_production(self) -> bool:
        return os.getenv("ENVIRONMENT", "development").lower() == "production"

    @property
    def authentication_enabled(self) -> bool:
        return bool(self.supabase_url and self.supabase_publishable_key)

    class Config:
        env_file = ".env"


settings = Settings()
