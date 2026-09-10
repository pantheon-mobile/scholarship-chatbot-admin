from __future__ import annotations

import os

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analytics import AccessLog, AnalyticsVisitor, ChatSession
from app.models.auth import AdminOperationLog
from app.models.data_source import DataSource
from app.models.faq import Faq
from app.repositories.data_source import DataSourceRepository
from app.services.ingestion_processor import DataSourceCleanupProcessor


class MaintenanceDisabledError(Exception):
    pass


class MaintenanceCleanupError(Exception):
    pass


def destructive_purge_enabled() -> bool:
    enabled = os.getenv("ENABLE_DESTRUCTIVE_PURGE", "false").lower() == "true"
    environment = os.getenv("APP_ENV", "").lower()
    return enabled and environment in {"development", "validation", "stg01-demo"}


class MaintenanceService:
    def __init__(self, session: AsyncSession, cleanup_processor: DataSourceCleanupProcessor | None) -> None:
        self.session = session
        self.cleanup_processor = cleanup_processor

    async def purge(self) -> dict[str, int]:
        if not destructive_purge_enabled():
            raise MaintenanceDisabledError()

        sources = await DataSourceRepository(self.session).list_all_for_cleanup()
        if sources and self.cleanup_processor:
            try:
                await self.cleanup_processor.cleanup(sources)
            except Exception as exc:
                raise MaintenanceCleanupError() from exc

        counts = {
            "data_sources": len(sources),
            "faqs": int((await self.session.execute(delete(Faq))).rowcount or 0),
            "chat_sessions": int((await self.session.execute(delete(ChatSession))).rowcount or 0),
            "access_logs": int((await self.session.execute(delete(AccessLog))).rowcount or 0),
            "operation_logs": int((await self.session.execute(delete(AdminOperationLog))).rowcount or 0),
        }
        # Child rows are removed by FK cascades. Visitors are analytics identities,
        # not authentication sessions, and are part of the requested log purge.
        await self.session.execute(delete(AnalyticsVisitor))
        await self.session.execute(delete(DataSource))
        await self.session.commit()
        return counts
