"""
Alembic migration environment configuration.

This module configures how Alembic runs migrations, supporting both
online (connected to database) and offline (SQL script generation) modes.
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from src.core.config.loader import get_config
from src.core.storage.postgres import Base

# Import all models to register them with Base.metadata
from src.core.models import security_digest  # noqa: F401

# Alembic Config object
config = context.config

# Configure logging from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata for autogenerate
target_metadata = Base.metadata


def get_database_url() -> str:
    """
    Build database URL from application configuration.

    Returns:
        PostgreSQL connection URL for async driver.
    """
    app_config = get_config()
    postgres_config = app_config.get("postgres", {})

    host = postgres_config.get("host", "localhost")
    port = postgres_config.get("port", 5432)
    database = postgres_config.get("database", "assistant")
    user = postgres_config.get("user", "assistant")
    password = postgres_config.get("password", "assistant")

    return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{database}"


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    Generates SQL script without connecting to the database.
    Useful for reviewing migrations before applying.
    """
    url = get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations with a database connection."""
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """
    Run migrations in 'online' mode with async engine.

    Creates an async engine and runs migrations within a connection.
    """
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_database_url()

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
