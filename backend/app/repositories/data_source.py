from __future__ import annotations

from datetime import datetime, timezone
from math import ceil

from sqlalchemy import delete, exists, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.repositories.data_source_mutation import (
    DataSourceMutationError, ensure_editable, lock_mutations, lock_sources, queue_refresh,
)
from app.models.category import Category
from app.models.classification import ClassificationType, ClassificationValue
from app.models.data_source import DataSource, DataSourceClassificationValue, DataSourceFile, DataSourceWebsite, IngestionJob
from app.schemas.data_source import DataSourceFilters, DeleteTarget, FileDataSourceUpdateRequest, WebsiteDataSourceUpdateRequest


class DataSourceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _conditions(filters: DataSourceFilters):
        conditions = []
        if filters.keyword:
            pattern = f"%{filters.keyword}%"
            conditions.append(or_(DataSource.title.ilike(pattern), DataSourceFile.file_name.ilike(pattern), DataSourceWebsite.url.ilike(pattern)))
        if filters.format:
            conditions.append(DataSource.format == filters.format)
        if filters.status:
            conditions.append(DataSource.status == filters.status)
        if filters.category_id == "UNSET":
            conditions.append(DataSource.category_id.is_(None))
        elif filters.category_id is not None:
            conditions.append(DataSource.category_id == filters.category_id)
        if filters.answer_source_enabled is not None:
            conditions.append(DataSource.answer_source_enabled == filters.answer_source_enabled)
        if filters.priority:
            conditions.append(DataSource.priority == filters.priority)
        if filters.reference_link_visible is not None:
            conditions.append(DataSource.reference_link_visible == filters.reference_link_visible)
        for type_code, value_id in (
            ("TYPE_1", filters.type_1_value_id),
            ("TYPE_2", filters.type_2_value_id),
            ("TYPE_3", filters.type_3_value_id),
        ):
            if value_id == "UNSET":
                conditions.append(~exists().where(
                    DataSourceClassificationValue.data_source_id == DataSource.id,
                    DataSourceClassificationValue.classification_type.has(type_code=type_code),
                ))
            elif value_id is not None:
                conditions.append(exists().where(
                    DataSourceClassificationValue.data_source_id == DataSource.id,
                    DataSourceClassificationValue.classification_value_id == value_id,
                    DataSourceClassificationValue.classification_type.has(type_code=type_code),
                ))
        return conditions

    @staticmethod
    def _base_query():
        return select(DataSource).outerjoin(DataSourceFile).outerjoin(DataSourceWebsite)

    async def list(self, filters: DataSourceFilters) -> tuple[list[DataSource], int, int, int]:
        conditions = self._conditions(filters)
        count_stmt = select(func.count(DataSource.id), func.coalesce(func.sum(DataSource.size_bytes), 0)).select_from(DataSource).outerjoin(DataSourceFile).outerjoin(DataSourceWebsite)
        if conditions:
            count_stmt = count_stmt.where(*conditions)
        total_count, total_size = (await self.session.execute(count_stmt)).one()
        total_count = int(total_count)
        total_pages = ceil(total_count / filters.page_size) if total_count else 0

        sort_columns = {"id": DataSource.id, "title": DataSource.title, "updated_at": DataSource.updated_at}
        sort_column = sort_columns[filters.sort]
        order_clause = sort_column.asc() if filters.order == "asc" else sort_column.desc()
        stmt = self._base_query().options(
            selectinload(DataSource.file),
            selectinload(DataSource.website),
            selectinload(DataSource.classification_links).selectinload(DataSourceClassificationValue.classification_type),
            selectinload(DataSource.classification_links).selectinload(DataSourceClassificationValue.classification_value),
        )
        if conditions:
            stmt = stmt.where(*conditions)
        stmt = stmt.order_by(order_clause, DataSource.id.asc()).offset((filters.page - 1) * filters.page_size).limit(filters.page_size)
        rows = list((await self.session.execute(stmt)).scalars().unique().all())
        return rows, total_count, total_pages, int(total_size or 0)

    async def get(self, data_source_id: int) -> DataSource | None:
        stmt = select(DataSource).where(DataSource.id == data_source_id).options(
            selectinload(DataSource.file),
            selectinload(DataSource.website),
            selectinload(DataSource.classification_links).selectinload(DataSourceClassificationValue.classification_type),
            selectinload(DataSource.classification_links).selectinload(DataSourceClassificationValue.classification_value),
        ).execution_options(populate_existing=True)
        return (await self.session.execute(stmt)).scalars().first()

    async def list_categories(self) -> list[Category]:
        statement = select(Category).order_by(Category.parent_id.nullsfirst(), Category.display_order, Category.id)
        return list((await self.session.execute(statement)).scalars().all())

    async def list_import_classifications(self) -> list[ClassificationType]:
        statement = select(ClassificationType).where(
            ClassificationType.type_code.in_(("TYPE_1", "TYPE_2", "TYPE_3"))
        ).options(selectinload(ClassificationType.values)).order_by(ClassificationType.display_order)
        return list((await self.session.execute(statement)).scalars().unique().all())

    async def get_for_update_many(self, ids: list[int]) -> list[DataSource]:
        if not ids:
            return []
        await lock_mutations(self.session)
        statement = select(DataSource).where(DataSource.id.in_(ids)).order_by(DataSource.id).with_for_update().execution_options(populate_existing=True).options(
            selectinload(DataSource.file), selectinload(DataSource.website),
            selectinload(DataSource.classification_links).selectinload(DataSourceClassificationValue.classification_type),
            selectinload(DataSource.classification_links).selectinload(DataSourceClassificationValue.classification_value),
        )
        return list((await self.session.execute(statement)).scalars().unique().all())

    async def get_for_deletion(self, ids: list[int]) -> list[DataSource]:
        # Hold the shared claim lock until cleanup and DB deletion commit.
        rows = await self.get_for_update_many(ids)
        running = set((await self.session.execute(select(IngestionJob.data_source_id).where(
            IngestionJob.data_source_id.in_(ids), IngestionJob.status == "RUNNING",
        ))).scalars().all())
        blocked = [row for row in rows if row.status == "TRAINING" or row.id in running]
        if blocked:
            targets = [{"id": row.id, "title": row.title, "status": row.status} for row in blocked]
            details = "、".join(f"ID:{row.id}「{row.title}」" for row in blocked)
            raise DataSourceMutationError(
                f"学習中のデータソースは削除できません：{details}。学習処理の完了後に再操作してください。",
                code="DATA_SOURCE_DELETE_BLOCKED", targets=targets,
            )
        return rows

    async def apply_import_updates(self, updates: list[dict]) -> None:
        rows = await lock_sources(self.session, DataSource.id.in_([item["id"] for item in updates]))
        now = datetime.now(timezone.utc)
        for item in updates:
            data_source_id = item["id"]
            await self.session.execute(update(DataSource).where(DataSource.id == data_source_id).values(
                title=item["title"], category_id=item["category_id"], priority=item["priority"],
                answer_source_enabled=item["answer_source_enabled"],
                reference_link_visible=item["reference_link_visible"],
                version=DataSource.version + 1, updated_at=now,
            ))
            await self.session.execute(delete(DataSourceClassificationValue).where(
                DataSourceClassificationValue.data_source_id == data_source_id
            ))
            self.session.add_all([DataSourceClassificationValue(
                data_source_id=data_source_id, classification_type_id=type_id,
                classification_value_id=value_id,
            ) for type_id, value_id in item["classifications"]])
            await self._enqueue_refresh_if_idle(data_source_id)
        await self.session.commit()

    async def category_exists(self, category_id: int) -> bool:
        await lock_mutations(self.session)
        statement = select(Category.id).where(Category.id == category_id).with_for_update(read=True)
        return (await self.session.execute(statement)).scalar_one_or_none() is not None

    async def update_toggle(self, data_source_id: int, field: str, value: bool, version: int) -> bool:
        if field not in {"answer_source_enabled", "reference_link_visible"}:
            raise ValueError("invalid_toggle_field")
        await lock_sources(self.session, DataSource.id == data_source_id)
        stmt = update(DataSource).where(DataSource.id == data_source_id, DataSource.version == version).values({
            field: value,
            "version": DataSource.version + 1,
            "updated_at": datetime.now(timezone.utc),
        })
        result = await self.session.execute(stmt)
        if result.rowcount != 1:
            await self.session.rollback()
            return False
        await self._enqueue_refresh_if_idle(data_source_id)
        await self.session.commit()
        return True

    async def delete_one(self, data_source_id: int, version: int) -> bool:
        result = await self.session.execute(delete(DataSource).where(DataSource.id == data_source_id, DataSource.version == version))
        if result.rowcount != 1:
            await self.session.rollback()
            return False
        await self.session.commit()
        return True

    async def bulk_delete(self, targets: list[DeleteTarget]) -> int:
        ids = [target.id for target in targets]
        rows = (await self.session.execute(select(DataSource.id, DataSource.version).where(DataSource.id.in_(ids)).with_for_update())).all()
        current = {row.id: row.version for row in rows}
        if len(current) != len(set(ids)):
            await self.session.rollback()
            raise LookupError("not_found")
        if len(ids) != len(set(ids)):
            await self.session.rollback()
            raise ValueError("duplicate_target")
        if any(current.get(target.id) != target.version for target in targets):
            await self.session.rollback()
            raise ValueError("version_mismatch")
        await self.session.execute(delete(DataSource).where(DataSource.id.in_(ids)))
        await self.session.commit()
        return len(ids)

    async def classification_value_matches_type(self, type_id: int, value_id: int) -> bool:
        stmt = select(func.count()).select_from(ClassificationValue).where(
            ClassificationValue.id == value_id,
            ClassificationValue.classification_type_id == type_id,
        )
        return (await self.session.execute(stmt)).scalar_one() == 1

    async def resolve_classification_value(self, type_code: str, value_id: int) -> tuple[int, int] | None:
        await lock_mutations(self.session)
        stmt = (
            select(ClassificationType.id, ClassificationValue.id)
            .join(ClassificationValue, ClassificationValue.classification_type_id == ClassificationType.id)
            .where(ClassificationType.type_code == type_code, ClassificationValue.id == value_id)
        )
        row = (await self.session.execute(stmt)).one_or_none()
        return (int(row[0]), int(row[1])) if row else None

    async def create_file_sources(
        self,
        files: list[dict],
        *,
        priority: str,
        answer_source_enabled: bool,
        reference_link_visible: bool,
        category_id: int | None,
        classifications: list[tuple[int, int]],
    ) -> list[int]:
        await lock_mutations(self.session)
        names = [item["file_name"] for item in files]
        if len(set(names)) != len(names):
            raise DataSourceMutationError("同名のファイルを一度に複数指定できません。", code="DATA_SOURCE_DUPLICATE")
        now = datetime.now(timezone.utc)
        rows: list[DataSource] = []
        for item in files:
            existing = await self._find_existing("FILE", item["file_name"])
            if existing is not None:
                item["previous_storage_key"] = existing.file.storage_key
                existing.file.storage_key = item["storage_key"]
                existing.file.mime_type = item["content_type"] or None
                existing.size_bytes = item["size_bytes"]
                existing.format = item["extension"]
                await self._replace_attributes(existing, title=item["title"], category_id=category_id,
                    priority=priority, answer_source_enabled=answer_source_enabled,
                    reference_link_visible=reference_link_visible, classifications=classifications)
                rows.append(existing)
                continue
            row = DataSource(
                source_type="FILE",
                title=item["title"],
                format=item["extension"],
                status="PREPARING",
                category_id=category_id,
                category_name=None,
                size_bytes=item["size_bytes"],
                character_count=None,
                answer_source_enabled=answer_source_enabled,
                priority=priority,
                reference_link_visible=reference_link_visible,
                updated_at=now,
                version=1,
                file=DataSourceFile(
                    file_name=item["file_name"],
                    storage_key=item["storage_key"],
                    mime_type=item["content_type"] or None,
                ),
                classification_links=[
                    DataSourceClassificationValue(
                        classification_type_id=type_id,
                        classification_value_id=value_id,
                    )
                    for type_id, value_id in classifications
                ],
            )
            self.session.add(row)
            rows.append(row)
        await self.session.flush()
        for row in rows:
            await self._enqueue_refresh_if_idle(int(row.id))
        return [int(row.id) for row in rows]

    async def update_file_attributes(
        self,
        data_source_id: int,
        payload: FileDataSourceUpdateRequest,
        title: str,
        classifications: list[tuple[int, int]],
    ) -> bool:
        await lock_sources(self.session, DataSource.id == data_source_id)
        stmt = (
            update(DataSource)
            .where(DataSource.id == data_source_id, DataSource.version == payload.version)
            .values(
                title=title,
                category_id=payload.category_id,
                priority=payload.priority,
                answer_source_enabled=payload.answer_source_enabled,
                reference_link_visible=payload.reference_link_visible,
                version=DataSource.version + 1,
                updated_at=datetime.now(timezone.utc),
            )
        )
        result = await self.session.execute(stmt)
        if result.rowcount != 1:
            await self.session.rollback()
            return False
        await self.session.execute(
            delete(DataSourceClassificationValue).where(
                DataSourceClassificationValue.data_source_id == data_source_id
            )
        )
        self.session.add_all([
            DataSourceClassificationValue(
                data_source_id=data_source_id,
                classification_type_id=type_id,
                classification_value_id=value_id,
            )
            for type_id, value_id in classifications
        ])
        await self._enqueue_refresh_if_idle(data_source_id)
        await self.session.commit()
        return True

    async def create_website_source(
        self,
        *,
        url: str,
        title: str,
        priority: str,
        answer_source_enabled: bool,
        reference_link_visible: bool,
        category_id: int | None,
        classifications: list[tuple[int, int]],
    ) -> int:
        existing = await self._find_existing("WEB", url)
        if existing is not None:
            await self._replace_attributes(existing, title=title, category_id=category_id,
                priority=priority, answer_source_enabled=answer_source_enabled,
                reference_link_visible=reference_link_visible, classifications=classifications)
            return int(existing.id)
        row = DataSource(
            source_type="WEB",
            title=title,
            format="Web",
            status="PREPARING",
            category_id=category_id,
            category_name=None,
            size_bytes=None,
            character_count=None,
            answer_source_enabled=answer_source_enabled,
            priority=priority,
            reference_link_visible=reference_link_visible,
            updated_at=datetime.now(timezone.utc),
            version=1,
            website=DataSourceWebsite(url=url, last_fetched_at=None),
            classification_links=[
                DataSourceClassificationValue(
                    classification_type_id=type_id,
                    classification_value_id=value_id,
                )
                for type_id, value_id in classifications
            ],
        )
        self.session.add(row)
        await self.session.flush()
        await self.enqueue_ingestion_jobs([int(row.id)], scheduled_at=datetime.now(timezone.utc))
        return int(row.id)

    async def enqueue_ingestion_jobs(
        self,
        data_source_ids: list[int],
        *,
        scheduled_at: datetime,
        max_attempts: int = 3,
    ) -> None:
        now = datetime.now(timezone.utc)
        self.session.add_all([
            IngestionJob(
                data_source_id=data_source_id,
                status="QUEUED",
                scheduled_at=scheduled_at,
                attempt_count=0,
                max_attempts=max_attempts,
                created_at=now,
                updated_at=now,
            )
            for data_source_id in data_source_ids
        ])

    async def _enqueue_refresh_if_idle(self, data_source_id: int) -> None:
        rows = await lock_sources(self.session, DataSource.id == data_source_id)
        await queue_refresh(self.session, rows)

    async def _find_existing(self, kind: str, identity: str) -> DataSource | None:
        await lock_mutations(self.session)
        model, column = (DataSourceFile, DataSourceFile.file_name) if kind == "FILE" else (DataSourceWebsite, DataSourceWebsite.url)
        ids = list((await self.session.execute(select(model.data_source_id).where(column == identity))).scalars().all())
        if len(ids) > 1:
            raise DataSourceMutationError(
                f"同じファイル名またはURLが複数登録されています（ID:{','.join(map(str, ids))}）。重複を解消してから再操作してください。",
                code="DATA_SOURCE_DUPLICATE",
            )
        if not ids:
            return None
        rows = await self.get_for_update_many(ids)
        ensure_editable(rows)
        return rows[0]

    async def _replace_attributes(self, row, *, title, category_id, priority,
                                  answer_source_enabled, reference_link_visible, classifications):
        row.title, row.category_id, row.category_name = title, category_id, None
        row.priority = priority
        row.answer_source_enabled = answer_source_enabled
        row.reference_link_visible = reference_link_visible
        row.character_count = None
        row.version += 1
        await self.session.execute(delete(DataSourceClassificationValue).where(
            DataSourceClassificationValue.data_source_id == row.id
        ))
        self.session.add_all([DataSourceClassificationValue(data_source_id=row.id,
            classification_type_id=type_id, classification_value_id=value_id)
            for type_id, value_id in classifications])
        await self.session.flush()
        await self._enqueue_refresh_if_idle(row.id)

    async def enqueue_refresh(self, data_source_id: int) -> None:
        await self._enqueue_refresh_if_idle(data_source_id)
        await self.session.commit()

    async def update_website_attributes(
        self,
        data_source_id: int,
        payload: WebsiteDataSourceUpdateRequest,
        *,
        url: str,
        title: str,
        classifications: list[tuple[int, int]],
    ) -> bool:
        await lock_sources(self.session, DataSource.id == data_source_id)
        duplicate_ids = list((await self.session.execute(select(DataSourceWebsite.data_source_id).where(
            DataSourceWebsite.url == url, DataSourceWebsite.data_source_id != data_source_id
        ))).scalars().all())
        if duplicate_ids:
            raise DataSourceMutationError(f"同じURLが既に登録されています（ID:{','.join(map(str, duplicate_ids))}）。既存データを編集してください。", code="DATA_SOURCE_DUPLICATE")
        result = await self.session.execute(
            update(DataSource)
            .where(DataSource.id == data_source_id, DataSource.version == payload.version)
            .values(
                title=title,
                category_id=payload.category_id,
                priority=payload.priority,
                answer_source_enabled=payload.answer_source_enabled,
                reference_link_visible=payload.reference_link_visible,
                version=DataSource.version + 1,
                updated_at=datetime.now(timezone.utc),
            )
        )
        if result.rowcount != 1:
            await self.session.rollback()
            return False
        website_result = await self.session.execute(
            update(DataSourceWebsite)
            .where(DataSourceWebsite.data_source_id == data_source_id)
            .values(url=url)
        )
        if website_result.rowcount != 1:
            raise LookupError("website_not_found")
        await self.session.execute(
            delete(DataSourceClassificationValue).where(
                DataSourceClassificationValue.data_source_id == data_source_id
            )
        )
        self.session.add_all([
            DataSourceClassificationValue(
                data_source_id=data_source_id,
                classification_type_id=type_id,
                classification_value_id=value_id,
            )
            for type_id, value_id in classifications
        ])
        await self._enqueue_refresh_if_idle(data_source_id)
        await self.session.commit()
        return True

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()
