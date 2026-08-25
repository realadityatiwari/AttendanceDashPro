import asyncio
from logging.config import fileConfig
import sys
import os
from configparser import Interpolation

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context
from app.db.base_class import Base
import app.models  # Ensure models are loaded

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Disable ConfigParser interpolation on the Alembic config parser.
#
# The production DATABASE_URI contains percent-encoded credential characters
# (e.g. '%23' for '#'). Alembic's Config creates its ConfigParser with the
# default BasicInterpolation, which interprets '%' sequences and raises
# `ValueError: invalid interpolation syntax` in set_main_option().
# Replacing `_interpolation` with the no-op `Interpolation` class (the same
# object configparser uses for `interpolation=None`) lets the URL pass through
# verbatim. `file_config` is memoized, so this is applied once before use.
config.file_config._interpolation = Interpolation()

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

from app.core.config import settings
config.set_main_option("sqlalchemy.url", settings.DATABASE_URI)

target_metadata = Base.metadata

def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()

def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()

async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()

def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
