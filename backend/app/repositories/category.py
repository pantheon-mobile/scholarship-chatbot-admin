from datetime import datetime, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category
from app.models.data_source import DataSource


class CategoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_all(self, *, for_update: bool = False) -> list[Category]:
        statement = select(Category).order_by(Category.parent_id.nullsfirst(), Category.display_order, Category.id)
        if for_update:
            statement = statement.with_for_update()
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def delete_ids(self, ids: set[int]) -> None:
        await self.session.execute(delete(Category).where(Category.id.in_(ids)))

    async def clear_data_source_categories(self, category_ids: set[int]) -> int:
        if not category_ids:
            return 0
        rows = list((await self.session.execute(
            select(DataSource).where(DataSource.category_id.in_(category_ids)).with_for_update()
        )).scalars().all())
        now = datetime.now(timezone.utc)
        for row in rows:
            row.category_id = None
            row.version += 1
            row.updated_at = now
        await self.session.flush()
        return len(rows)

    async def name_exists(self, parent_id: int | None, name: str, *, exclude_id: int | None = None) -> bool:
        statement = select(func.count()).select_from(Category).where(Category.name == name)
        statement = statement.where(Category.parent_id.is_(None)) if parent_id is None else statement.where(Category.parent_id == parent_id)
        if exclude_id is not None:
            statement = statement.where(Category.id != exclude_id)
        return (await self.session.execute(statement)).scalar_one() > 0

    async def add(self, name: str, parent_id: int | None, display_order: int) -> Category:
        now = datetime.now(timezone.utc)
        category = Category(
            name=name,
            parent_id=parent_id,
            display_order=display_order,
            version=1,
            created_at=now,
            updated_at=now,
        )
        self.session.add(category)
        await self.session.flush()
        return category

    async def update_category(
        self,
        category: Category,
        *,
        name: str,
        parent_id: int | None,
        display_order: int,
        old_siblings_to_shift: list[Category],
    ) -> None:
        now = datetime.now(timezone.utc)
        for sibling in old_siblings_to_shift:
            sibling.display_order -= 1
            sibling.version += 1
            sibling.updated_at = now
        category.name = name
        category.parent_id = parent_id
        category.display_order = display_order
        category.version += 1
        category.updated_at = now
        await self.session.flush()

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()

    async def reorder(self, rows: list[Category], ordered_ids: list[int]) -> None:
        by_id = {row.id: row for row in rows}
        now = datetime.now(timezone.utc)
        for display_order, category_id in enumerate(ordered_ids, start=1):
            category = by_id[category_id]
            if category.display_order == display_order:
                continue
            category.display_order = display_order
            category.version += 1
            category.updated_at = now

    async def flush(self) -> None:
        await self.session.flush()
