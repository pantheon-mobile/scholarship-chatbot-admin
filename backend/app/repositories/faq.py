from __future__ import annotations

from datetime import datetime, timezone
from math import ceil

from sqlalchemy import delete, exists, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.faq import Faq, FaqClassificationAssignment, FaqSimilarQuestion
from app.models.faq_classification import FaqClassificationType, FaqClassificationValue
from app.schemas.faq import FaqDeleteTarget, FaqFilters


class FaqRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def conditions(filters: FaqFilters, type_ids: dict[str, int]):
        conditions = []
        if filters.keyword:
            pattern = f"%{filters.keyword}%"
            conditions.append(or_(Faq.question.ilike(pattern), Faq.answer.ilike(pattern)))
        if filters.chat_enabled is not None:
            conditions.append(Faq.chat_enabled == filters.chat_enabled)
        for index in range(1, 5):
            value_id = getattr(filters, f"classification_{index}_value_id")
            if value_id is not None:
                conditions.append(exists().where(
                    FaqClassificationAssignment.faq_id == Faq.id,
                    FaqClassificationAssignment.classification_type_id == type_ids[f"FAQ_TYPE_{index}"],
                    FaqClassificationAssignment.classification_value_id == value_id,
                ))
        return conditions

    async def resolve_value_type(self, type_code: str, value_id: int) -> int | None:
        row = (await self.session.execute(
            select(FaqClassificationType.id)
            .join(FaqClassificationValue, FaqClassificationValue.classification_type_id == FaqClassificationType.id)
            .where(FaqClassificationType.type_code == type_code, FaqClassificationValue.id == value_id)
        )).scalar_one_or_none()
        return int(row) if row is not None else None

    async def get_value_type(self, value_id: int) -> tuple[int, str] | None:
        row = (await self.session.execute(
            select(FaqClassificationType.id, FaqClassificationType.type_code)
            .join(FaqClassificationValue, FaqClassificationValue.classification_type_id == FaqClassificationType.id)
            .where(FaqClassificationValue.id == value_id)
        )).one_or_none()
        return (int(row.id), str(row.type_code)) if row else None

    async def list_type_labels(self) -> dict[str, str]:
        rows = (await self.session.execute(
            select(FaqClassificationType.type_code, FaqClassificationType.display_label)
            .order_by(FaqClassificationType.display_order)
        )).all()
        return {str(row.type_code): str(row.display_label) for row in rows}

    async def list_import_classifications(self) -> list[FaqClassificationType]:
        return list((await self.session.execute(
            select(FaqClassificationType)
            .options(selectinload(FaqClassificationType.values))
            .order_by(FaqClassificationType.display_order)
        )).scalars().unique().all())

    async def get_for_update_many(self, faq_ids: list[int]) -> list[Faq]:
        if not faq_ids:
            return []
        return list((await self.session.execute(
            select(Faq).where(Faq.id.in_(faq_ids)).with_for_update()
        )).scalars().all())

    async def list(self, filters: FaqFilters, type_ids: dict[str, int], *, paginate: bool = True) -> tuple[list[Faq], int, int]:
        conditions = self.conditions(filters, type_ids)
        count_stmt = select(func.count(Faq.id))
        if conditions:
            count_stmt = count_stmt.where(*conditions)
        total_count = int((await self.session.execute(count_stmt)).scalar_one())
        total_pages = ceil(total_count / filters.page_size) if total_count else 0
        sort_column = {"id": Faq.id, "updated_at": Faq.updated_at}[filters.sort]
        order_clause = sort_column.asc() if filters.order == "asc" else sort_column.desc()
        stmt = select(Faq).options(
            selectinload(Faq.classification_assignments).selectinload(FaqClassificationAssignment.classification_type),
            selectinload(Faq.classification_assignments).selectinload(FaqClassificationAssignment.classification_value),
        ).order_by(order_clause, Faq.id.asc())
        if conditions:
            stmt = stmt.where(*conditions)
        if paginate:
            stmt = stmt.offset((filters.page - 1) * filters.page_size).limit(filters.page_size)
        rows = list((await self.session.execute(stmt)).scalars().unique().all())
        return rows, total_count, total_pages

    async def get(self, faq_id: int) -> Faq | None:
        return (await self.session.execute(select(Faq).where(Faq.id == faq_id))).scalars().first()

    async def get_detail(self, faq_id: int) -> Faq | None:
        stmt = select(Faq).where(Faq.id == faq_id).options(
            selectinload(Faq.similar_questions),
            selectinload(Faq.classification_assignments).selectinload(FaqClassificationAssignment.classification_type),
            selectinload(Faq.classification_assignments).selectinload(FaqClassificationAssignment.classification_value),
        ).execution_options(populate_existing=True)
        return (await self.session.execute(stmt)).scalars().unique().first()

    async def create(
        self,
        *,
        question: str,
        answer: str,
        similar_questions: list[str],
        classifications: list[tuple[int, int]],
        chat_enabled: bool,
    ) -> int:
        row = Faq(
            question=question,
            answer=answer,
            chat_enabled=chat_enabled,
            version=1,
            similar_questions=[
                FaqSimilarQuestion(question=value, display_order=index)
                for index, value in enumerate(similar_questions, start=1)
            ],
            classification_assignments=[
                FaqClassificationAssignment(classification_type_id=type_id, classification_value_id=value_id)
                for type_id, value_id in classifications
            ],
        )
        self.session.add(row)
        await self.session.flush()
        return int(row.id)

    async def update(
        self,
        faq_id: int,
        *,
        version: int,
        question: str,
        answer: str,
        similar_questions: list[str],
        classifications: list[tuple[int, int]],
        chat_enabled: bool,
    ) -> bool:
        result = await self.session.execute(
            update(Faq)
            .where(Faq.id == faq_id, Faq.version == version)
            .values(
                question=question,
                answer=answer,
                chat_enabled=chat_enabled,
                version=Faq.version + 1,
                updated_at=datetime.now(timezone.utc),
            )
        )
        if result.rowcount != 1:
            await self.session.rollback()
            return False

        await self.session.execute(delete(FaqSimilarQuestion).where(FaqSimilarQuestion.faq_id == faq_id))
        await self.session.execute(
            delete(FaqClassificationAssignment).where(FaqClassificationAssignment.faq_id == faq_id)
        )
        self.session.add_all([
            FaqSimilarQuestion(faq_id=faq_id, question=value, display_order=index)
            for index, value in enumerate(similar_questions, start=1)
        ])
        self.session.add_all([
            FaqClassificationAssignment(
                faq_id=faq_id,
                classification_type_id=type_id,
                classification_value_id=value_id,
            )
            for type_id, value_id in classifications
        ])
        await self.session.flush()
        return True

    async def delete_one(self, faq_id: int, version: int) -> bool:
        result = await self.session.execute(delete(Faq).where(Faq.id == faq_id, Faq.version == version))
        if result.rowcount != 1:
            await self.session.rollback()
            return False
        await self.session.commit()
        return True

    async def bulk_delete(self, targets: list[FaqDeleteTarget]) -> int:
        ids = [target.id for target in targets]
        if len(ids) != len(set(ids)):
            await self.session.rollback()
            raise ValueError("duplicate_target")
        rows = (await self.session.execute(select(Faq.id, Faq.version).where(Faq.id.in_(ids)).with_for_update())).all()
        current = {int(row.id): int(row.version) for row in rows}
        if len(current) != len(ids):
            await self.session.rollback()
            raise LookupError("not_found")
        if any(current[target.id] != target.version for target in targets):
            await self.session.rollback()
            raise ValueError("version_mismatch")
        await self.session.execute(delete(Faq).where(Faq.id.in_(ids)))
        await self.session.commit()
        return len(ids)

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()
