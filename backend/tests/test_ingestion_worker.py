from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.ingestion_processor import IngestionResult
from app.services.ingestion_worker import IngestionWorker


def job(job_id: int = 1):
    return SimpleNamespace(
        id=job_id,
        data_source=SimpleNamespace(id=10, source_type="FILE", format="pdf"),
    )


@pytest.mark.anyio
async def test_worker_processes_jobs_until_queue_is_empty():
    repository = AsyncMock()
    repository.claim_next.side_effect = [job(1), job(2), None]
    processor = AsyncMock()
    processor.process.side_effect = [
        IngestionResult(character_count=120),
        IngestionResult(character_count=240),
    ]

    result = await IngestionWorker(
        repository, processor, worker_id="test-worker"
    ).run_until_empty()

    assert result.processed == 2
    assert result.succeeded == 2
    assert result.failed == 0
    assert repository.claim_next.await_count == 3
    assert repository.claim_next.await_args_list[0].args == ("test-worker",)
    assert repository.mark_succeeded.await_args_list[0].kwargs == {"character_count": 120}
    assert repository.mark_succeeded.await_args_list[1].kwargs == {"character_count": 240}


@pytest.mark.anyio
async def test_worker_records_failure_without_stopping_other_jobs():
    repository = AsyncMock()
    repository.claim_next.side_effect = [job(1), job(2), None]
    repository.mark_failed.return_value = "QUEUED"
    processor = AsyncMock()
    processor.process.side_effect = [RuntimeError("conversion failed"), IngestionResult()]

    result = await IngestionWorker(repository, processor).run_until_empty()

    assert result.processed == 2
    assert result.succeeded == 1
    assert result.failed == 1
    repository.mark_failed.assert_awaited_once_with(
        1, error_code="RuntimeError", error_message="conversion failed"
    )
    repository.mark_succeeded.assert_awaited_once_with(2, character_count=None)


@pytest.mark.anyio
async def test_worker_honors_max_jobs():
    repository = AsyncMock()
    repository.claim_next.side_effect = [job(1), job(2)]
    processor = AsyncMock()
    processor.process.return_value = IngestionResult()

    result = await IngestionWorker(repository, processor).run_until_empty(max_jobs=1)

    assert result.processed == 1
    assert repository.claim_next.await_count == 1
