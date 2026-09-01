from __future__ import annotations

import logging
import socket
from dataclasses import dataclass

from app.repositories.ingestion_job import IngestionJobRepository
from app.services.ingestion_processor import IngestionProcessor


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WorkerRunResult:
    processed: int
    succeeded: int
    failed: int


class IngestionWorker:
    def __init__(
        self,
        repository: IngestionJobRepository,
        processor: IngestionProcessor,
        *,
        worker_id: str | None = None,
    ) -> None:
        self.repository = repository
        self.processor = processor
        self.worker_id = worker_id or socket.gethostname()

    async def run_until_empty(self, *, max_jobs: int = 1000) -> WorkerRunResult:
        processed = succeeded = failed = 0
        while processed < max_jobs:
            job = await self.repository.claim_next(self.worker_id)
            if job is None:
                break
            processed += 1
            try:
                result = await self.processor.process(job.data_source)
                await self.repository.mark_succeeded(
                    job.id, character_count=result.character_count
                )
                succeeded += 1
                logger.info("ingestion job succeeded", extra={"job_id": job.id})
            except Exception as exc:
                failed += 1
                status = await self.repository.mark_failed(
                    job.id,
                    error_code=type(exc).__name__,
                    error_message=str(exc) or type(exc).__name__,
                )
                logger.exception(
                    "ingestion job failed",
                    extra={"job_id": job.id, "next_status": status},
                )
        return WorkerRunResult(processed=processed, succeeded=succeeded, failed=failed)
