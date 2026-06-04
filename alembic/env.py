from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context
from figure_data.config import load_settings
from figure_data.db import models
from figure_data.db.base import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = load_settings()
config.set_main_option("sqlalchemy.url", settings.database_url)
target_metadata = Base.metadata
_MODEL_MODULES = models.__all__
FIGURE_DATA_SCHEMA = "figure_data"


def run_migrations_offline() -> None:
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
        version_table_schema=FIGURE_DATA_SCHEMA,
    )
    with context.begin_transaction():
        context.execute(f"CREATE SCHEMA IF NOT EXISTS {FIGURE_DATA_SCHEMA}")
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
            version_table_schema=FIGURE_DATA_SCHEMA,
        )
        with context.begin_transaction():
            context.execute(f"CREATE SCHEMA IF NOT EXISTS {FIGURE_DATA_SCHEMA}")
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
