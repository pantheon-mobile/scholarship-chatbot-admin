from __future__ import annotations

from datetime import datetime, timezone
from math import ceil

from sqlalchemy import delete, exists, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.classification import ClassificationType, ClassificationValue
from app.models.data_source import DataSource, DataSourceClassificationValue, DataSourceFile, DataSourceWebsite
from app.schemas.data_source import DataSourceFilters, DeleteTarget, FileDataSourceUpdateRequest


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
            if value_id is not None:
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

    async def update_toggle(self, data_source_id: int, field: str, value: bool, version: int) -> bool:
        if field not in {"answer_source_enabled", "reference_link_visible"}:
            raise ValueError("invalid_toggle_field")
        stmt = update(DataSource).where(DataSource.id == data_source_id, DataSource.version == version).values({
            field: value,
            "version": DataSource.version + 1,
            "updated_at": datetime.now(timezone.utc),
        })
        result = await self.session.execute(stmt)
        if result.rowcount != 1:
            await self.session.rollback()
            return False
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
        classifications: list[tuple[int, int]],
    ) -> list[int]:
        now = datetime.now(timezone.utc)
        rows: list[DataSource] = []
        for item in files:
            row = DataSource(
                source_type="FILE",
                title=item["title"],
                format=item["extension"],
                status="PREPARING",
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
        return [int(row.id) for row in rows]

    async def update_file_attributes(
        self,
        data_source_id: int,
        payload: FileDataSourceUpdateRequest,
        title: str,
        classifications: list[tuple[int, int]],
    ) -> bool:
        stmt = (
            update(DataSource)
            .where(DataSource.id == data_source_id, DataSource.version == payload.version)
            .values(
                title=title,
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
        classifications: list[tuple[int, int]],
    ) -> int:
        row = DataSource(
            source_type="WEB",
            title=title,
            format="Web",
            status="PREPARING",
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
        return int(row.id)

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()
