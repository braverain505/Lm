#!/usr/bin/env python3
"""Alembic environment — resolves the app's database URL from settings."""
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.config import settings
from app.models import Base  # noqa: F401 — imported for accurate metadata

config = context.config

# The API's startup schema sync (app/core/schema_sync.py) imports this env
# *in-process* and sets skip_logging_config. fileConfig() would otherwise
# replace the root handler and drop the process to WARN, silencing every INFO
# log the app emits for the rest of its life — including the ones the Render
# deploy log is read for. The app has already configured logging, so leave it.
if config.config_file_name is not None and not config.attributes.get(
    "skip_logging_config", False
):
    fileConfig(config.config_file_name)

# Inject the runtime URL (from env / .env) instead of the INI placeholder.
config.set_main_option("sqlalchemy.url", settings.database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
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
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()