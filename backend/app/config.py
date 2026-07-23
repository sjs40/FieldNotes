from pathlib import Path
import os
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = Field(default=f"sqlite:///{Path(__file__).parents[2] / 'fieldnotes.db'}", validation_alias=AliasChoices("DATABASE_URL", "POSTGRES_URL"))
    quote_cache_minutes: int = 15
    default_benchmark: str = "SPY"
    allow_yfinance: bool = True
    supabase_url: str | None = Field(default=None, validation_alias=AliasChoices("SUPABASE_URL", "NEXT_PUBLIC_SUPABASE_URL"))
    supabase_publishable_key: str | None = Field(default=None, validation_alias=AliasChoices("SUPABASE_PUBLISHABLE_KEY", "SUPABASE_ANON_KEY", "NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY", "NEXT_PUBLIC_SUPABASE_ANON_KEY"))

    @property
    def is_production(self) -> bool:
        return os.getenv("ENVIRONMENT", "development").lower() == "production" or os.getenv("VERCEL_ENV", "").lower() == "production"

    @property
    def authentication_enabled(self) -> bool:
        return bool(self.supabase_url and self.supabase_publishable_key)

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
