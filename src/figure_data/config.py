from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8-sig",
        extra="ignore",
        populate_by_name=True,
    )

    database_url: str = Field(alias="DATABASE_URL")
    cbdb_sqlite_path: Path = Path("figure-data/cbdb_20260530.sqlite3")
    cbdb_metadata_path: Path = Path("figure-data/cbdb_20260530.json")
    source_snapshot: str = "cbdb_20260530"
    source_name: str = "cbdb"
    neo4j_uri: str | None = Field(default=None, alias="NEO4J_URI")
    neo4j_user: str | None = Field(default=None, alias="NEO4J_USER")
    neo4j_password: str | None = Field(default=None, alias="NEO4J_PASSWORD")
    neo4j_database: str = Field(default="neo4j", alias="NEO4J_DATABASE")
    ai_enabled: bool = Field(default=False, alias="FIGURE_AI_ENABLED")
    ai_provider: str | None = Field(default=None, alias="FIGURE_AI_PROVIDER")
    ai_model: str | None = Field(default=None, alias="FIGURE_AI_MODEL")
    ai_api_key: str | None = Field(default=None, alias="FIGURE_AI_API_KEY")
    ai_base_url: str | None = Field(default=None, alias="FIGURE_AI_BASE_URL")
    ai_timeout_seconds: float = Field(default=30.0, alias="FIGURE_AI_TIMEOUT_SECONDS")
    ai_max_output_tokens: int = Field(default=1200, alias="FIGURE_AI_MAX_OUTPUT_TOKENS")
    redis_url: str | None = Field(default=None, alias="REDIS_URL")
    ai_queue_backend: str = Field(default="database", alias="FIGURE_AI_QUEUE_BACKEND")
    ai_queue_name: str = Field(default="figure-ai", alias="FIGURE_AI_QUEUE_NAME")
    ai_job_timeout_seconds: int = Field(default=120, alias="FIGURE_AI_JOB_TIMEOUT_SECONDS")
    ai_job_max_retries: int = Field(default=2, alias="FIGURE_AI_JOB_MAX_RETRIES")
    ai_job_retry_base_seconds: int = Field(default=10, alias="FIGURE_AI_JOB_RETRY_BASE_SECONDS")
    ai_rate_limit_per_minute: int = Field(default=20, alias="FIGURE_AI_RATE_LIMIT_PER_MINUTE")
    embedding_provider: str = Field(default="fake", alias="FIGURE_EMBEDDING_PROVIDER")
    embedding_model: str = Field(
        default="fake-hash-embedding",
        alias="FIGURE_EMBEDDING_MODEL",
    )
    embedding_dimensions: int = Field(default=8, alias="FIGURE_EMBEDDING_DIMENSIONS")
    embedding_batch_size: int = Field(default=16, alias="FIGURE_EMBEDDING_BATCH_SIZE")

    def __init__(self, **data: object) -> None:
        super().__init__(**data)  # type: ignore[arg-type]

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, value: object) -> object:
        if isinstance(value, str) and value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+psycopg://", 1)
        return value

    @field_validator("ai_provider", "ai_model", "ai_api_key", "ai_base_url", mode="before")
    @classmethod
    def normalize_optional_ai_text(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value

    @field_validator("redis_url", mode="before")
    @classmethod
    def normalize_optional_redis_url(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value

    @field_validator("ai_queue_backend", mode="before")
    @classmethod
    def normalize_ai_queue_backend(cls, value: object) -> object:
        if isinstance(value, str):
            backend = value.strip().lower()
            if backend in {"database", "rq"}:
                return backend
        raise ValueError("FIGURE_AI_QUEUE_BACKEND must be 'database' or 'rq'")

    @field_validator("embedding_provider", "embedding_model", mode="before")
    @classmethod
    def normalize_required_embedding_text(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            if stripped:
                return stripped
        return value


@lru_cache(maxsize=1)
def load_settings() -> Settings:
    return Settings()
