from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.faq_classification import FaqClassificationType, FaqClassificationValue
from app.schemas.faq_classification import FaqClassificationOrderItem


class FaqClassificationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_types(self) -> list[FaqClassificationType]:
        result = await self.session.execute(
            select(FaqClassificationType)
            .options(joinedload(FaqClassificationType.values))
            .order_by(FaqClassificationType.display_order)
        )
        return list(result.scalars().unique().all())

    async def get_type(self, type_id: int) -> FaqClassificationType | None:
        result = await self.session.execute(
            select(FaqClassificationType)
            .where(FaqClassificationType.id == type_id)
            .options(joinedload(FaqClassificationType.values))
            .execution_options(populate_existing=True)
        )
        return result.scalars().first()

    async def get_value(self, value_id: int) -> FaqClassificationValue | None:
        result = await self.session.execute(
            select(FaqClassificationValue).where(FaqClassificationValue.id == value_id)
        )
        return result.scalars().first()

    async def value_name_exists(self, type_id: int, value_name: str, *, exclude_id: int | None = None) -> bool:
        statement = select(func.count()).select_from(FaqClassificationValue).where(
            FaqClassificationValue.classification_type_id == type_id,
            FaqClassificationValue.value_name == value_name,
        )
        if exclude_id is not None:
            statement = statement.where(FaqClassificationValue.id != exclude_id)
        return (await self.session.execute(statement)).scalar_one() > 0

    async def update_label(self, type_id: int, display_label: str, version: int) -> bool:
        result = await self.session.execute(
            update(FaqClassificationType)
            .where(FaqClassificationType.id == type_id, FaqClassificationType.version == version)
            .values(
                display_label=display_label,
                version=FaqClassificationType.version + 1,
                updated_at=datetime.now(timezone.utc),
            )
        )
        return result.rowcount == 1

    async def add_value(self, type_id: int, value_name: str) -> FaqClassificationValue:
        await self.session.execute(
            select(FaqClassificationType.id)
            .where(FaqClassificationType.id == type_id)
            .with_for_update()
        )
        max_order = (await self.session.execute(
            select(func.coalesce(func.max(FaqClassificationValue.display_order), 0))
            .where(FaqClassificationValue.classification_type_id == type_id)
        )).scalar_one()
        now = datetime.now(timezone.utc)
        value = FaqClassificationValue(
            classification_type_id=type_id,
            value_name=value_name,
            display_order=max_order + 1,
            version=1,
            created_at=now,
            updated_at=now,
        )
        self.session.add(value)
        await self.session.flush()
        return value

    async def update_value(self, type_id: int, value_id: int, value_name: str, version: int) -> bool:
        result = await self.session.execute(
            update(FaqClassificationValue)
            .where(
                FaqClassificationValue.id == value_id,
                FaqClassificationValue.classification_type_id == type_id,
                FaqClassificationValue.version == version,
            )
            .values(
                value_name=value_name,
                version=FaqClassificationValue.version + 1,
                updated_at=datetime.now(timezone.utc),
            )
        )
        return result.rowcount == 1

    async def delete_value(self, type_id: int, value_id: int, version: int) -> bool:
        result = await self.session.execute(
            delete(FaqClassificationValue).where(
                FaqClassificationValue.id == value_id,
                FaqClassificationValue.classification_type_id == type_id,
                FaqClassificationValue.version == version,
            )
        )
        return result.rowcount == 1

    async def reorder_values(self, type_id: int, items: list[FaqClassificationOrderItem]) -> str | None:
        requested_ids = [item.id for item in items]
        if len(requested_ids) != len(set(requested_ids)):
            return "invalid_order"
        requested_rows = list((await self.session.execute(
            select(FaqClassificationValue)
            .where(FaqClassificationValue.id.in_(requested_ids))
            .with_for_update()
        )).scalars().all())
        if any(row.classification_type_id != type_id for row in requested_rows):
            return "cross_type"
        all_rows = list((await self.session.execute(
            select(FaqClassificationValue)
            .where(FaqClassificationValue.classification_type_id == type_id)
            .with_for_update()
        )).scalars().all())
        if set(requested_ids) != {row.id for row in all_rows}:
            return "invalid_order"
        by_id = {row.id: row for row in all_rows}
        if any(by_id[item.id].version != item.version for item in items):
            return "version_mismatch"
        now = datetime.now(timezone.utc)
        for display_order, item in enumerate(items, start=1):
            row = by_id[item.id]
            if row.display_order != display_order:
                row.display_order = display_order
                row.version += 1
                row.updated_at = now
        await self.session.flush()
        return None

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()
