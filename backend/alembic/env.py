"""
Alembic migration environment.

This file runs whenever you execute any `alembic` command.
It connects to the database and applies or rolls back schema changes.

We use the SYNCHRONOUS psycopg2 driver here because Alembic does not
support asyncpg natively. The async driver (asyncpg) is used at runtime
by FastAPI; psycopg2 is only used during migrations.
"""

import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# Load .env file so DATABASE_URL is available
from dotenv import load_dotenv

load_dotenv()

# This is the Alembic Config object
config = context.config

# Set up Python logging from the alembic.ini [loggers] section
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import the Base metadata from our app so Alembic can detect all models.
# IMPORTANT: We must import ALL model modules here, otherwise Alembic
# won't know they exist and will miss them in auto-generated migrations.
from app.database import Base  # noqa: E402
import app.models.submission  # noqa: F401, E402
import app.models.analyst     # noqa: F401, E402
import app.models.analysis    # noqa: F401, E402
import app.models.audit       # noqa: F401, E402

target_metadata = Base.metadata


def get_database_url() -> str:
    """
    Build the synchronous PostgreSQL URL for Alembic from the DATABASE_URL env var.

    The app uses 'postgresql+asyncpg://' for async operations, but Alembic
    needs the sync 'postgresql+psycopg2://' driver.
    """
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        raise ValueError(
            "DATABASE_URL environment variable is not set. "
            "Make sure you have a .env file or the variable is exported."
        )
    # Convert async URL to sync URL for Alembic
    url = url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
    url = url.replace("postgresql+asyncpg:", "postgresql+psycopg2:")
    return url


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    In offline mode, Alembic generates SQL scripts without connecting to
    the database. Useful for reviewing what will change before applying it.
    """
    url = get_database_url()
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
    """
    Run migrations in 'online' mode.

    In online mode, Alembic connects directly to the database and applies
    changes immediately. This is the normal mode used in development and CI.
    """
    # Override the placeholder URL in alembic.ini with the real one
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_database_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,  # Don't use connection pooling during migrations
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
