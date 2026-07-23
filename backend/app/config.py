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
    sentry_dsn: str | None = Field(default=None, validation_alias="SENTRY_DSN")
    sentry_environment: str | None = Field(default=None, validation_alias="SENTRY_ENVIRONMENT")
    sentry_traces_sample_rate: float = Field(default=0.0, validation_alias="SENTRY_TRACES_SAMPLE_RATE")
    ibkr_sync_token: str | None = Field(default=None, validation_alias="FIELDNOTES_IBKR_SYNC_TOKEN")

    @property
    def is_production(self) -> bool:
        return os.getenv("ENVIRONMENT", "development").lower() == "production" or os.getenv("VERCEL_ENV", "").lower() == "production"

    @property
    def authentication_enabled(self) -> bool:
        return bool(self.supabase_url and self.supabase_publishable_key)

    def validate_production(self) -> None:
        if self.is_production and not self.authentication_enabled:
            raise RuntimeError("Supabase authentication must be configured in production")

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
