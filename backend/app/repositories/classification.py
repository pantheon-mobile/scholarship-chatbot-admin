from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.classification import ClassificationType, ClassificationValue


class ClassificationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_types(self) -> list[ClassificationType]:
        result = await self.session.execute(
            select(ClassificationType)
            .options(joinedload(ClassificationType.values))
            .order_by(ClassificationType.display_order)
        )
        return result.scalars().unique().all()

    async def get_type(self, type_id: int) -> ClassificationType | None:
        result = await self.session.execute(
            select(ClassificationType)
            .where(ClassificationType.id == type_id)
            .options(joinedload(ClassificationType.values))
        )
        return result.scalars().first()

    async def get_value(self, value_id: int, type_id: int | None = None) -> ClassificationValue | None:
        stmt = select(ClassificationValue).where(ClassificationValue.id == value_id)
        if type_id is not None:
            stmt = stmt.where(ClassificationValue.classification_type_id == type_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def value_name_exists(self, type_id: int, value_name: str, exclude_id: int | None = None) -> bool:
        stmt = select(func.count()).select_from(ClassificationValue).where(
            ClassificationValue.classification_type_id == type_id,
            ClassificationValue.value_name == value_name,
        )
        if exclude_id is not None:
            stmt = stmt.where(ClassificationValue.id != exclude_id)
        result = await self.session.execute(stmt)
        return result.scalar_one() > 0

    async def update_type_label(self, type_id: int, label: str, expected_version: int) -> ClassificationType:
        stmt = (
            update(ClassificationType)
            .where(ClassificationType.id == type_id)
            .where(ClassificationType.version == expected_version)
            .values(display_label=label, version=ClassificationType.version + 1, updated_at=datetime.now(timezone.utc))
        )
        result = await self.session.execute(stmt)
        if result.rowcount != 1:
            raise ValueError("version_mismatch")
        await self.session.commit()
        updated = await self.get_type(type_id)
        assert updated is not None
        return updated

    async def add_value(self, type_id: int, value_name: str) -> ClassificationValue:
        max_order_stmt = (
            select(func.coalesce(func.max(ClassificationValue.display_order), 0))
            .where(ClassificationValue.classification_type_id == type_id)
        )
        max_order = (await self.session.execute(max_order_stmt)).scalar_one()
        new_value = ClassificationValue(
            classification_type_id=type_id,
            value_name=value_name,
            display_order=max_order + 1,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            version=1,
        )
        self.session.add(new_value)
        await self.session.commit()
        await self.session.refresh(new_value)
        return new_value

    async def update_value(self, value_id: int, type_id: int, value_name: str, expected_version: int) -> None:
        stmt = (
            update(ClassificationValue)
            .where(ClassificationValue.id == value_id)
            .where(ClassificationValue.classification_type_id == type_id)
            .where(ClassificationValue.version == expected_version)
            .values(value_name=value_name, version=ClassificationValue.version + 1, updated_at=datetime.now(timezone.utc))
        )
        result = await self.session.execute(stmt)
        if result.rowcount != 1:
            raise ValueError("version_mismatch")
        await self.session.commit()

    async def delete_value(self, value_id: int, type_id: int, expected_version: int) -> None:
        stmt = (
            delete(ClassificationValue)
            .where(ClassificationValue.id == value_id)
            .where(ClassificationValue.classification_type_id == type_id)
            .where(ClassificationValue.version == expected_version)
        )
        result = await self.session.execute(stmt)
        if result.rowcount != 1:
            raise ValueError("version_mismatch")
        await self.session.commit()

    async def reorder_values(self, type_id: int, ordered_ids: list[int]) -> None:
        result = await self.session.execute(
            select(ClassificationValue)
            .where(ClassificationValue.classification_type_id == type_id)
        )
        rows = {item.id: item for item in result.scalars().all()}
        if set(rows.keys()) != set(ordered_ids):
            raise ValueError("invalid_order")

        for index, value_id in enumerate(ordered_ids, start=1):
            rows[value_id].display_order = index
        await self.session.commit()
