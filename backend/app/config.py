from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = Field(default=f"sqlite:///{Path(__file__).parents[2] / 'fieldnotes.db'}")
    quote_cache_minutes: int = 15
    default_benchmark: str = "SPY"
    allow_yfinance: bool = True

    class Config:
        env_file = ".env"


settings = Settings()
