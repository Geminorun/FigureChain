from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    database_url: str = Field(alias="DATABASE_URL")
    cbdb_sqlite_path: Path = Path("figure-data/cbdb_20260530.sqlite3")
    cbdb_metadata_path: Path = Path("figure-data/cbdb_20260530.json")
    source_snapshot: str = "cbdb_20260530"
    source_name: str = "cbdb"

    def __init__(self, **data: object) -> None:
        super().__init__(**data)  # type: ignore[arg-type]

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, value: object) -> object:
        if isinstance(value, str) and value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+psycopg://", 1)
        return value


@lru_cache(maxsize=1)
def load_settings() -> Settings:
    return Settings()
