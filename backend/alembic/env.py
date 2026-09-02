from logging.config import fileConfig
import os

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

from app.db.base_class import Base
from app.models.classification import ClassificationType, ClassificationValue
from app.models.data_source import DataSource, DataSourceClassificationValue, DataSourceFile, DataSourceWebsite, IngestionJob
from app.models.category import Category
from app.models.faq_classification import FaqClassificationType, FaqClassificationValue
from app.models.faq import Faq, FaqClassificationAssignment, FaqSimilarQuestion
from app.models.analytics import AccessLog, AnalyticsVisitor, ChatFeedback, ChatInteraction, ChatSession
from app.models.auth import AdminOperationLog, AuthSession, CpfUsedJti

config = context.config
fileConfig(config.config_file_name)

config.set_main_option(
    "sqlalchemy.url",
    os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@db:5432/scholarship"),
)

target_metadata = Base.metadata


def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations():
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online():
    import asyncio
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
