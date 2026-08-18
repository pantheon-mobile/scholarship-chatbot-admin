from collections import defaultdict
from io import BytesIO

from openpyxl import Workbook

from app.models.category import Category
from app.repositories.category import CategoryRepository
from app.schemas.category import CategoryDeleteTarget, CategoryOrderRequest, CategoryResponse


class CategoryNotFoundError(Exception):
    pass


class CategoryVersionConflictError(Exception):
    pass


class InvalidCategoryOrderError(Exception):
    pass


class CrossParentReorderError(Exception):
    pass


class EmptyCategorySelectionError(Exception):
    pass


class DuplicateCategoryNameError(Exception):
    pass


class CategoryService:
    def __init__(self, repository: CategoryRepository) -> None:
        self.repository = repository

    @staticmethod
    def _children(rows: list[Category]) -> dict[int | None, list[Category]]:
        children: dict[int | None, list[Category]] = defaultdict(list)
        for row in rows:
            children[row.parent_id].append(row)
        for siblings in children.values():
            siblings.sort(key=lambda row: (row.display_order, row.id))
        return children

    @classmethod
    def _responses(cls, rows: list[Category]) -> list[CategoryResponse]:
        children = cls._children(rows)
        return [CategoryResponse(
            id=row.id,
            name=row.name,
            parent_id=row.parent_id,
            display_order=row.display_order,
            version=row.version,
            has_children=bool(children.get(row.id)),
            created_at=row.created_at,
            updated_at=row.updated_at,
        ) for row in rows]

    @staticmethod
    def _descendant_ids(root_ids: set[int], children: dict[int | None, list[Category]]) -> set[int]:
        result: set[int] = set()
        stack = list(root_ids)
        while stack:
            category_id = stack.pop()
            if category_id in result:
                continue
            result.add(category_id)
            stack.extend(child.id for child in children.get(category_id, []))
        return result

    async def list_categories(self) -> list[CategoryResponse]:
        return self._responses(await self.repository.list_all())

    @staticmethod
    def normalize_name(name: str) -> str:
        normalized = name.strip()
        if not normalized or len(normalized) > 15:
            raise ValueError("invalid_category_name")
        return normalized

    async def validate_name_available(self, name: str, parent_id: int | None, *, exclude_id: int | None = None) -> str:
        normalized = self.normalize_name(name)
        if await self.repository.name_exists(parent_id, normalized, exclude_id=exclude_id):
            raise DuplicateCategoryNameError()
        return normalized

    async def delete(self, category_id: int, version: int) -> None:
        rows = await self.repository.list_all(for_update=True)
        by_id = {row.id: row for row in rows}
        category = by_id.get(category_id)
        if category is None:
            await self.repository.rollback()
            raise CategoryNotFoundError()
        if category.version != version:
            await self.repository.rollback()
            raise CategoryVersionConflictError()
        delete_ids = self._descendant_ids({category_id}, self._children(rows))
        await self.repository.delete_ids(delete_ids)
        await self.repository.commit()

    async def bulk_delete(self, targets: list[CategoryDeleteTarget]) -> int:
        if not targets:
            raise EmptyCategorySelectionError()
        rows = await self.repository.list_all(for_update=True)
        by_id = {row.id: row for row in rows}
        for target in targets:
            category = by_id.get(target.id)
            if category is None:
                await self.repository.rollback()
                raise CategoryNotFoundError()
            if category.version != target.version:
                await self.repository.rollback()
                raise CategoryVersionConflictError()
        delete_ids = self._descendant_ids({target.id for target in targets}, self._children(rows))
        await self.repository.delete_ids(delete_ids)
        await self.repository.commit()
        return len(delete_ids)

    async def reorder(self, payload: CategoryOrderRequest) -> list[CategoryResponse]:
        if not payload.items:
            raise InvalidCategoryOrderError()
        rows = await self.repository.list_all(for_update=True)
        by_id = {row.id: row for row in rows}
        request_ids = [item.id for item in payload.items]
        if len(request_ids) != len(set(request_ids)):
            await self.repository.rollback()
            raise InvalidCategoryOrderError()
        for item in payload.items:
            category = by_id.get(item.id)
            if category is not None and category.parent_id != payload.parent_id:
                await self.repository.rollback()
                raise CrossParentReorderError()
        siblings = [row for row in rows if row.parent_id == payload.parent_id]
        if set(request_ids) != {row.id for row in siblings}:
            await self.repository.rollback()
            raise InvalidCategoryOrderError()
        for item in payload.items:
            category = by_id.get(item.id)
            if category is None:
                await self.repository.rollback()
                raise InvalidCategoryOrderError()
            if category.version != item.version:
                await self.repository.rollback()
                raise CategoryVersionConflictError()
        await self.repository.reorder(siblings, request_ids)
        await self.repository.flush()
        await self.repository.commit()
        updated = await self.repository.list_all()
        return [row for row in self._responses(updated) if row.parent_id == payload.parent_id]

    @classmethod
    def validate_parent_change(cls, category_id: int, parent_id: int | None, rows: list[Category]) -> None:
        if parent_id is None:
            return
        if parent_id == category_id:
            raise ValueError("category_cycle")
        descendants = cls._descendant_ids({category_id}, cls._children(rows))
        if parent_id in descendants:
            raise ValueError("category_cycle")

    async def export_excel(self) -> bytes:
        rows = await self.repository.list_all()
        children = self._children(rows)
        flattened: list[tuple[Category, list[str]]] = []

        def visit(parent_id: int | None, path: list[str]) -> None:
            for category in children.get(parent_id, []):
                category_path = [*path, category.name]
                flattened.append((category, category_path))
                visit(category.id, category_path)

        visit(None, [])
        max_depth = max((len(path) for _, path in flattened), default=1)
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = "カテゴリ一覧"
        worksheet.append(["ID", *[f"カテゴリ{depth}" for depth in range(1, max_depth + 1)]])
        for category, path in flattened:
            worksheet.append([category.id, *path, *([""] * (max_depth - len(path)))])
        output = BytesIO()
        workbook.save(output)
        return output.getvalue()
