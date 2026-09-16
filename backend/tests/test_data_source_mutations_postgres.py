"""PostgreSQL regression tests. Set TEST_DATABASE_URL to a disposable test DB."""
import os
from datetime import datetime, timezone

import pytest
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

from app.db.base_class import Base
from app.models.category import Category
from app.models.classification import ClassificationType, ClassificationValue
from app.models.data_source import DataSource, DataSourceClassificationValue, IngestionJob
from app.repositories.category import CategoryRepository
from app.repositories.classification import ClassificationRepository
from app.repositories.data_source import DataSourceRepository
from app.repositories.data_source_mutation import DataSourceMutationError
from app.repositories.ingestion_job import IngestionJobRepository
from app.schemas.category import CategoryUpdateRequest
from app.schemas.data_source import FileDataSourceUpdateRequest, WebsiteDataSourceUpdateRequest
from app.services.category_service import CategoryService

pytestmark = [pytest.mark.anyio, pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="requires test PostgreSQL")]


@pytest.fixture
async def db():
    engine = create_async_engine(os.environ["TEST_DATABASE_URL"])
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with engine.connect() as connection:
        transaction = await connection.begin()
        async with AsyncSession(connection, expire_on_commit=False, join_transaction_mode="create_savepoint") as session:
            yield session
        await transaction.rollback()
    await engine.dispose()


async def seed(db, *, kind="FILE", status="AVAILABLE", category_id=None, classifications=None, name="same.pdf"):
    repo = DataSourceRepository(db)
    kwargs = dict(priority="MEDIUM", answer_source_enabled=True, reference_link_visible=True,
                  category_id=category_id, classifications=classifications or [])
    if kind == "FILE":
        ids = await repo.create_file_sources([dict(title="同じタイトル", file_name=name, storage_key="old.pdf",
            extension="pdf", size_bytes=10, content_type="application/pdf")], **kwargs)
        source_id = ids[0]
    else:
        source_id = await repo.create_website_source(url=name, title="同じタイトル", **kwargs)
    row = await repo.get(source_id)
    row.status = status
    job = (await db.execute(select(IngestionJob).where(IngestionJob.data_source_id == source_id))).scalar_one()
    job.status = {"AVAILABLE": "SUCCEEDED", "TRAINING": "RUNNING", "ERROR": "FAILED", "PREPARING": "QUEUED"}[status]
    await db.commit()
    return row


@pytest.mark.parametrize("status", ["AVAILABLE", "PREPARING", "TRAINING", "ERROR"])
@pytest.mark.parametrize("method", ["toggle", "file", "web", "import"])
async def test_source_mutations_enforce_status_at_write(db, status, method):
    row = await seed(db, kind="WEB" if method == "web" else "FILE", status=status,
                     name="https://example.com/a" if method == "web" else "same.pdf")
    source_id = row.id
    repo = DataSourceRepository(db)
    async def mutate():
        if method == "toggle":
            return await repo.update_toggle(row.id, "reference_link_visible", False, row.version)
        if method == "file":
            return await repo.update_file_attributes(row.id, FileDataSourceUpdateRequest(version=row.version, title="変更", priority="HIGH", answer_source_enabled=True, reference_link_visible=True), "変更", [])
        if method == "web":
            return await repo.update_website_attributes(row.id, WebsiteDataSourceUpdateRequest(version=row.version, url="https://example.com/a", title="変更", priority="HIGH", answer_source_enabled=True, reference_link_visible=True), url="https://example.com/a", title="変更", classifications=[])
        return await repo.apply_import_updates([dict(id=row.id, title="変更", category_id=None, priority="HIGH",
            answer_source_enabled=True, reference_link_visible=True, classifications=[])])
    if status in {"TRAINING", "ERROR"}:
        with pytest.raises(DataSourceMutationError, match=f"ID:{row.id}"):
            await mutate()
        await db.rollback()
        assert (await repo.get(source_id)).status == status
        assert (await repo.get(source_id)).title == "同じタイトル"
    else:
        await mutate()
        assert (await repo.get(source_id)).status == "PREPARING"
        count = await db.scalar(select(func.count()).select_from(IngestionJob).where(
            IngestionJob.data_source_id == row.id, IngestionJob.status == "QUEUED"))
        assert count == 1


@pytest.mark.parametrize("kind,name", [("FILE", "same.pdf"), ("WEB", "https://example.com/a")])
@pytest.mark.parametrize("status", ["AVAILABLE", "PREPARING", "TRAINING", "ERROR"])
async def test_same_identity_replaces_only_editable_sources(db, kind, name, status):
    row = await seed(db, kind=kind, status=status, name=name)
    source_id = row.id
    repo = DataSourceRepository(db)
    kwargs = dict(priority="HIGH", answer_source_enabled=False, reference_link_visible=False, category_id=None, classifications=[])
    async def replace():
        if kind == "WEB":
            return await repo.create_website_source(url=name, title="差替後", **kwargs)
        records = [dict(title="差替後", file_name=name, storage_key="new.pdf", extension="pdf", size_bytes=100, content_type="application/pdf")]
        ids = await repo.create_file_sources(records, **kwargs)
        assert records[0]["previous_storage_key"] == "old.pdf"
        return ids[0]
    if status in {"TRAINING", "ERROR"}:
        with pytest.raises(DataSourceMutationError):
            await replace()
        await db.rollback()
        updated = await repo.get(source_id)
        assert updated.status == status and updated.title == "同じタイトル"
        if kind == "FILE": assert updated.file.storage_key == "old.pdf"
    else:
        assert await replace() == row.id
        await db.commit()
        updated = await repo.get(source_id)
        assert updated.title == "差替後" and updated.status == "PREPARING"
        assert updated.priority == "HIGH" and updated.answer_source_enabled is False
        if kind == "FILE": assert updated.file.storage_key == "new.pdf" and updated.size_bytes == 100
        assert await db.scalar(select(func.count()).select_from(DataSource)) == 1
        assert await db.scalar(select(func.count()).select_from(IngestionJob).where(IngestionJob.status == "QUEUED")) == 1


async def categories(db):
    parent = Category(name="親", parent_id=None, display_order=1, version=1)
    db.add(parent)
    await db.flush()
    child = Category(name="子", parent_id=parent.id, display_order=1, version=1)
    db.add(child)
    await db.commit()
    return parent, child


@pytest.mark.parametrize("action", ["rename", "delete"])
@pytest.mark.parametrize("status", ["AVAILABLE", "PREPARING", "TRAINING", "ERROR"])
async def test_category_changes_include_descendants_and_are_atomic(db, action, status):
    parent, child = await categories(db)
    row = await seed(db, category_id=child.id, status=status)
    service = CategoryService(CategoryRepository(db))
    async def change():
        if action == "rename":
            await service.update(parent.id, CategoryUpdateRequest(name="変更親", version=parent.version))
        else: await service.delete(parent.id, parent.version)
    if status in {"TRAINING", "ERROR"}:
        parent_id, row_id = parent.id, row.id
        with pytest.raises(DataSourceMutationError): await change()
        await db.rollback()
        assert (await db.get(Category, parent_id)).name == "親"
        assert (await DataSourceRepository(db).get(row_id)).status == status
    else:
        await change()
        updated = await DataSourceRepository(db).get(row.id)
        assert updated.status == "PREPARING"
        if action == "delete": assert updated.category_id is None and updated.category_name is None
        else:
            job = await IngestionJobRepository(db).claim_next("test-worker")
            assert job.data_source._ingestion_category_path == "変更親>子"


async def classification(db):
    item = ClassificationType(type_code="TYPE_1", fixed_name="種別1", display_label="種別1", display_order=1, version=1)
    db.add(item)
    await db.flush()
    value = ClassificationValue(classification_type_id=item.id, value_name="値", display_order=1, version=1)
    db.add(value)
    await db.commit()
    return item, value


@pytest.mark.parametrize("action", ["rename", "delete"])
@pytest.mark.parametrize("status", ["AVAILABLE", "PREPARING", "TRAINING", "ERROR"])
async def test_classification_changes_queue_or_block_all(db, action, status):
    item, value = await classification(db)
    row = await seed(db, status=status, classifications=[(item.id, value.id)])
    repo = ClassificationRepository(db)
    async def change():
        if action == "rename": await repo.update_value(value.id, item.id, "新しい値", value.version)
        else: await repo.delete_value(value.id, item.id, value.version)
    if status in {"TRAINING", "ERROR"}:
        value_id, row_id = value.id, row.id
        with pytest.raises(DataSourceMutationError): await change()
        await db.rollback()
        assert (await db.get(ClassificationValue, value_id)).value_name == "値"
        assert (await DataSourceRepository(db).get(row_id)).status == status
    else:
        await change()
        updated = await DataSourceRepository(db).get(row.id)
        assert updated.status == "PREPARING"
        if action == "delete": assert updated.classification_links == []
        else: assert updated.classification_links[0].classification_value.value_name == "新しい値"


async def test_label_changes_do_not_touch_training_sources(db):
    item, value = await classification(db)
    row = await seed(db, status="TRAINING", classifications=[(item.id, value.id)])
    await ClassificationRepository(db).update_type_label(item.id, "ラベル変更", item.version)
    assert (await DataSourceRepository(db).get(row.id)).status == "TRAINING"


async def test_duplicate_titles_are_allowed(db):
    one = await seed(db, name="one.pdf")
    two = await seed(db, name="two.pdf")
    assert one.id != two.id and one.title == two.title


async def test_master_block_does_not_queue_other_eligible_sources(db):
    parent, child = await categories(db)
    good = await seed(db, name="good.pdf", category_id=child.id)
    blocked = await seed(db, name="blocked.pdf", category_id=child.id, status="TRAINING")
    good_id, blocked_id, parent_id = good.id, blocked.id, parent.id
    with pytest.raises(DataSourceMutationError) as error:
        await CategoryService(CategoryRepository(db)).delete(parent.id, parent.version)
    assert error.value.targets == [{"id": blocked_id, "title": "同じタイトル", "status": "TRAINING"}]
    await db.rollback()
    assert (await DataSourceRepository(db).get(good_id)).status == "AVAILABLE"
    assert await db.get(Category, parent_id) is not None
    assert await db.scalar(select(func.count()).select_from(IngestionJob).where(IngestionJob.status == "QUEUED")) == 0


async def test_replacement_keeps_id_and_updates_classification(db):
    item, value = await classification(db)
    source = await seed(db, classifications=[(item.id, value.id)])
    source_id = source.id
    new_value = ClassificationValue(classification_type_id=item.id, value_name="差替種別", display_order=2, version=1)
    db.add(new_value)
    await db.commit()
    repo = DataSourceRepository(db)
    ids = await repo.create_file_sources([dict(title="差替", file_name="same.pdf", storage_key="new.pdf",
        extension="pdf", size_bytes=12, content_type="application/pdf")], category_id=None, priority="HIGH",
        answer_source_enabled=True, reference_link_visible=True, classifications=[(item.id, new_value.id)])
    await db.commit()
    assert ids == [source_id]
    updated = await repo.get(source_id)
    assert len(updated.classification_links) == 1
    assert updated.classification_links[0].classification_value.value_name == "差替種別"


async def test_worker_claim_waits_for_edit_and_reads_latest_content():
    import asyncio
    from uuid import uuid4
    from sqlalchemy import delete
    from app.repositories.data_source_mutation import lock_mutations
    engine = create_async_engine(os.environ["TEST_DATABASE_URL"])
    source_id = None
    claim_task = None
    try:
        async with AsyncSession(engine, expire_on_commit=False) as writer, AsyncSession(engine, expire_on_commit=False) as worker:
            row = await seed(writer, name=f"concurrency-{uuid4()}.pdf", status="PREPARING")
            source_id = row.id
            await lock_mutations(writer)
            row.title = "編集後の最新タイトル"
            await writer.flush()
            claim_task = asyncio.create_task(IngestionJobRepository(worker).claim_next("concurrency-test"))
            await asyncio.sleep(0.05)
            assert not claim_task.done()
            await writer.commit()
            job = await asyncio.wait_for(claim_task, timeout=5)
            assert job.data_source.id == source_id
            assert job.data_source.title == "編集後の最新タイトル"
            with pytest.raises(DataSourceMutationError):
                await DataSourceRepository(writer).update_toggle(source_id, "reference_link_visible", False, job.data_source.version)
            await writer.rollback()
    finally:
        if claim_task and not claim_task.done():
            claim_task.cancel()
        if source_id:
            async with engine.begin() as conn:
                await conn.execute(delete(DataSource).where(DataSource.id == source_id))
        await engine.dispose()


async def test_website_batch_rolls_back_earlier_replacements_on_blocked_row(db):
    from app.schemas.data_source import WebsiteDataSourceCreateRequest
    from app.services.data_source_service import DataSourceService
    first = await seed(db, kind="WEB", name="https://example.com/first")
    second = await seed(db, kind="WEB", name="https://example.com/second", status="ERROR")
    first_id, second_id = first.id, second.id
    with pytest.raises(DataSourceMutationError):
        await DataSourceService(DataSourceRepository(db)).create_website_sources([
            WebsiteDataSourceCreateRequest(url="https://example.com/first", title="上書き"),
            WebsiteDataSourceCreateRequest(url="https://example.com/second", title="拒否"),
        ])
    assert (await DataSourceRepository(db).get(first_id)).title == "同じタイトル"
    assert (await DataSourceRepository(db).get(first_id)).status == "AVAILABLE"
    assert (await DataSourceRepository(db).get(second_id)).status == "ERROR"


async def test_unchanged_import_skips_training_and_error_rows(db):
    from io import BytesIO
    from fastapi import UploadFile
    from app.schemas.data_source import DataSourceFilters
    from app.services.data_source_service import DataSourceService
    one = await seed(db, status="TRAINING", name="one.pdf")
    two = await seed(db, status="ERROR", name="two.pdf")
    one_id, two_id = one.id, two.id
    service = DataSourceService(DataSourceRepository(db))
    data = await service.export_excel(DataSourceFilters())
    result = await service.import_excel(UploadFile(filename="list.xlsx", file=BytesIO(data)))
    assert result.updated_count == 0
    assert (await DataSourceRepository(db).get(one_id)).status == "TRAINING"
    assert (await DataSourceRepository(db).get(two_id)).status == "ERROR"


async def test_legacy_duplicate_filename_is_not_arbitrarily_overwritten(db):
    from app.models.data_source import DataSourceFile
    row = await seed(db)
    # Simulate records permitted by the previous append-only implementation.
    duplicate = DataSource(source_type="FILE", title="重複", format="pdf", status="AVAILABLE", priority="MEDIUM",
        updated_at=datetime.now(timezone.utc), file=DataSourceFile(file_name="same.pdf", storage_key="duplicate.pdf"))
    db.add(duplicate)
    await db.commit()
    source_id, duplicate_id = row.id, duplicate.id
    with pytest.raises(DataSourceMutationError, match="複数"):
        await DataSourceRepository(db).create_file_sources([dict(title="上書き", file_name="same.pdf", storage_key="new.pdf",
            extension="pdf", size_bytes=10, content_type="application/pdf")], category_id=None, classifications=[],
            priority="MEDIUM", answer_source_enabled=True, reference_link_visible=True)
    await db.rollback()
    assert (await DataSourceRepository(db).get(source_id)).file.storage_key == "old.pdf"
    assert (await DataSourceRepository(db).get(duplicate_id)).file.storage_key == "duplicate.pdf"


async def test_blocked_category_api_explains_target_and_preserves_master(db):
    from httpx import AsyncClient, ASGITransport
    from app.main import app
    from app.api.v1.categories import get_service
    parent, child = await categories(db)
    source = await seed(db, status="ERROR", category_id=child.id)
    parent_id, source_id = parent.id, source.id
    app.dependency_overrides[get_service] = lambda: CategoryService(CategoryRepository(db))
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.put(f"/api/v1/categories/{parent_id}", json={"name": "変更", "version": parent.version})
        assert response.status_code == 409
        detail = response.json()["detail"]
        assert detail["targets"][0]["id"] == source_id
        assert "エラー" in detail["message"] and str(source_id) in detail["message"]
        await db.rollback()
        assert (await db.get(Category, parent_id)).name == "親"
    finally:
        app.dependency_overrides.pop(get_service, None)
