from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.data_source import DataSource, IngestionJob


class IngestionJobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def claim_next(self, worker_id: str) -> IngestionJob | None:
        now = datetime.now(timezone.utc)
        statement = (
            select(IngestionJob)
            .where(
                IngestionJob.status == "QUEUED",
                IngestionJob.scheduled_at <= now,
                IngestionJob.attempt_count < IngestionJob.max_attempts,
            )
            .options(
                selectinload(IngestionJob.data_source).selectinload(DataSource.file),
                selectinload(IngestionJob.data_source).selectinload(DataSource.website),
            )
            .order_by(IngestionJob.scheduled_at, IngestionJob.id)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        job = (await self.session.execute(statement)).scalars().first()
        if job is None:
            await self.session.rollback()
            return None

        job.status = "RUNNING"
        job.started_at = now
        job.completed_at = None
        job.attempt_count += 1
        job.worker_id = worker_id
        job.error_code = None
        job.error_message = None
        job.updated_at = now
        job.data_source.status = "TRAINING"
        job.data_source.updated_at = now
        job.data_source.version += 1
        await self.session.commit()
        return job

    async def mark_succeeded(self, job_id: int, *, character_count: int | None = None) -> None:
        job = await self._get_for_update(job_id)
        now = datetime.now(timezone.utc)
        job.status = "SUCCEEDED"
        job.completed_at = now
        job.updated_at = now
        job.data_source.status = "AVAILABLE"
        if character_count is not None:
            job.data_source.character_count = character_count
        if job.data_source.website is not None:
            job.data_source.website.last_fetched_at = now
        job.data_source.updated_at = now
        job.data_source.version += 1
        await self.session.commit()

    async def mark_failed(self, job_id: int, *, error_code: str, error_message: str) -> str:
        job = await self._get_for_update(job_id)
        now = datetime.now(timezone.utc)
        exhausted = job.attempt_count >= job.max_attempts
        job.status = "FAILED" if exhausted else "QUEUED"
        job.scheduled_at = now if exhausted else now + timedelta(minutes=5 * job.attempt_count)
        job.completed_at = now if exhausted else None
        job.error_code = error_code[:100]
        job.error_message = error_message[:4000]
        job.updated_at = now
        job.data_source.status = "ERROR" if exhausted else "PREPARING"
        job.data_source.updated_at = now
        job.data_source.version += 1
        await self.session.commit()
        return job.status

    async def _get_for_update(self, job_id: int) -> IngestionJob:
        statement = (
            select(IngestionJob)
            .where(IngestionJob.id == job_id)
            .options(
                selectinload(IngestionJob.data_source).selectinload(DataSource.website),
            )
            .with_for_update()
        )
        return (await self.session.execute(statement)).scalar_one()
