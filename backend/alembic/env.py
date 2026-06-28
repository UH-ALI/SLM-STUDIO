import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# ----------------- CUSTOM CONFIGURATION START -----------------

# 1. Add the project root to the system path
# This allows Alembic to see your 'app' folder
sys.path.append(os.getcwd())

# 2. Import your models and database connection
from app.models import Base
from app.core.config import settings

# 3. Read the Alembic config object
config = context.config

# 4. Setup Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name) 

# 5. OVERRIDE the URL in alembic.ini with the one from your .env file
# This ensures we use the Docker database credentials
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# 6. Link the 'Target Metadata'
# This tells Alembic: "Compare the database against THIS Python blueprint"
target_metadata = Base.metadata

# ----------------- CUSTOM CONFIGURATION END -----------------


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.
    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.
    Calls to context.execute() here emit the given string to the
    script output.

    without offline, the creation of database will be done under the hood
    with offline enabled, it will print the sql code which it is about to run
    this way we can read the code to make sure that the alembic isnt doing 
    something crazy.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.
    In this scenario we need to create an Engine
    and associate a connection with the context.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()