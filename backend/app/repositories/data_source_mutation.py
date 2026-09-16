"""Serialize short metadata writes with worker claims; never lock during AI processing."""
from datetime import datetime, timezone

from sqlalchemy import select, text

from app.models.data_source import DataSource, IngestionJob


class DataSourceMutationError(Exception):
    def __init__(self, message: str, *, code: str = "DATA_SOURCE_UPDATE_BLOCKED", targets=None):
        super().__init__(message)
        self.code = code
        self.targets = targets or []


async def lock_mutations(session) -> None:
    # Transaction-scoped, shared by master edits, source writes and ingestion claims.
    await session.execute(text("SELECT pg_advisory_xact_lock(724031, 1)"))


def ensure_editable(rows) -> None:
    labels = {"TRAINING": "学習中", "ERROR": "エラー"}
    blocked = [row for row in rows if row.status not in {"AVAILABLE", "PREPARING"}]
    if blocked:
        targets = [{"id": row.id, "title": row.title, "status": row.status} for row in blocked]
        details = "、".join(f"ID:{row.id}「{row.title}」（{labels.get(row.status, row.status)}）" for row in blocked)
        raise DataSourceMutationError(
            f"変更できないデータソースがあります：{details}。学習中は処理完了後、エラーは削除後に再操作してください。",
            targets=targets,
        )


async def lock_sources(session, condition):
    await lock_mutations(session)
    rows = list((await session.execute(select(DataSource).where(condition).order_by(DataSource.id)
        .with_for_update().execution_options(populate_existing=True))).scalars().all())
    ensure_editable(rows)
    return rows


async def queue_refresh(session, rows) -> None:
    ensure_editable(rows)
    now = datetime.now(timezone.utc)
    for row in rows:
        jobs = list((await session.execute(select(IngestionJob).where(
            IngestionJob.data_source_id == row.id,
            IngestionJob.status.in_(("QUEUED", "RUNNING")),
        ))).scalars().all())
        if any(job.status == "RUNNING" for job in jobs):
            raise DataSourceMutationError(f"ID:{row.id}「{row.title}」は学習処理中です。完了後に再操作してください。")
        if not jobs:
            session.add(IngestionJob(data_source_id=row.id, status="QUEUED", scheduled_at=now,
                attempt_count=0, max_attempts=3, created_at=now, updated_at=now))
        else:
            for job in jobs:
                job.attempt_count = 0
                job.scheduled_at = now
                job.error_code = job.error_message = None
        row.status = "PREPARING"
        row.updated_at = now
