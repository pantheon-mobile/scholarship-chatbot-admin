from __future__ import annotations

import asyncio
import logging
import os

from app.core.db import SessionLocal
from app.repositories.ingestion_job import IngestionJobRepository
from app.services.ingestion_processor import AwsIngestionProcessor, HttpIngestionProcessor
from app.services.ingestion_worker import IngestionWorker


async def main() -> None:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    processor_mode = os.getenv("INGESTION_PROCESSOR_MODE", "aws").strip().lower()
    if processor_mode == "http":
        processor_url = os.getenv("INGESTION_PROCESSOR_URL", "").strip()
        if not processor_url:
            raise RuntimeError("INGESTION_PROCESSOR_URL is required in http mode")
        timeout_seconds = float(os.getenv("INGESTION_PROCESSOR_TIMEOUT_SECONDS", "1800"))
        processor = HttpIngestionProcessor(processor_url, timeout_seconds=timeout_seconds)
    elif processor_mode == "aws":
        processor = AwsIngestionProcessor()
    else:
        raise RuntimeError(f"Unsupported INGESTION_PROCESSOR_MODE: {processor_mode}")
    max_jobs = int(os.getenv("INGESTION_WORKER_MAX_JOBS", "1000"))
    async with SessionLocal() as session:
        worker = IngestionWorker(
            IngestionJobRepository(session),
            processor,
        )
        result = await worker.run_until_empty(max_jobs=max_jobs)
        logging.info(
            "worker completed: processed=%s succeeded=%s failed=%s",
            result.processed,
            result.succeeded,
            result.failed,
        )


if __name__ == "__main__":
    asyncio.run(main())
