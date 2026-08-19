from io import BytesIO
from zoneinfo import ZoneInfo

from openpyxl import Workbook

from app.models.faq import Faq
from app.repositories.faq import FaqRepository
from app.schemas.faq import (
    FaqBulkDeleteRequest,
    FaqClassificationResponse,
    FaqFilters,
    FaqListResponse,
    FaqResponse,
)


class FaqError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class FaqService:
    def __init__(self, repository: FaqRepository) -> None:
        self.repository = repository

    async def validate_filters(self, filters: FaqFilters) -> dict[str, int]:
        type_ids: dict[str, int] = {}
        for index in range(1, 5):
            type_code = f"FAQ_TYPE_{index}"
            value_id = getattr(filters, f"classification_{index}_value_id")
            if value_id is not None:
                type_id = await self.repository.resolve_value_type(type_code, value_id)
                if type_id is None:
                    raise FaqError("INVALID_FAQ_CLASSIFICATION", "指定された区分値が正しくありません。")
                type_ids[type_code] = type_id
        return type_ids

    @staticmethod
    def serialize(row: Faq) -> FaqResponse:
        assignments = sorted(row.classification_assignments, key=lambda item: item.classification_type.display_order)
        return FaqResponse(
            id=row.id,
            question=row.question,
            answer=row.answer,
            chat_enabled=row.chat_enabled,
            updated_at=row.updated_at,
            version=row.version,
            classifications=[FaqClassificationResponse(
                type_code=item.classification_type.type_code,
                classification_type_id=item.classification_type_id,
                classification_value_id=item.classification_value_id,
                display_label=item.classification_type.display_label,
                value_name=item.classification_value.value_name,
            ) for item in assignments],
        )

    async def list(self, filters: FaqFilters) -> FaqListResponse:
        type_ids = await self.validate_filters(filters)
        rows, total_count, total_pages = await self.repository.list(filters, type_ids)
        if total_count and filters.page > total_pages:
            raise FaqError("PAGE_NOT_FOUND", "ページがありません。")
        return FaqListResponse(
            items=[self.serialize(row) for row in rows], page=filters.page, page_size=filters.page_size,
            total_count=total_count, total_pages=total_pages, sort=filters.sort, order=filters.order,
        )

    async def delete(self, faq_id: int, version: int) -> None:
        row = await self.repository.get(faq_id)
        if row is None:
            raise FaqError("FAQ_NOT_FOUND", "指定されたFAQが見つかりません。")
        if not await self.repository.delete_one(faq_id, version):
            raise FaqError("FAQ_VERSION_CONFLICT", "他の操作で情報が更新されています。再読み込みしてください。")

    async def bulk_delete(self, payload: FaqBulkDeleteRequest) -> int:
        try:
            return await self.repository.bulk_delete(payload.items)
        except LookupError:
            raise FaqError("FAQ_NOT_FOUND", "削除対象のFAQが見つかりません。") from None
        except ValueError as error:
            if str(error) == "version_mismatch":
                raise FaqError("FAQ_VERSION_CONFLICT", "他の操作で情報が更新されています。再読み込みしてください。") from None
            raise FaqError("INVALID_FAQ_DELETE_TARGETS", "削除対象が不正です。") from None

    async def export_excel(self, filters: FaqFilters, labels: dict[str, str]) -> bytes:
        type_ids = await self.validate_filters(filters)
        rows, _, _ = await self.repository.list(filters, type_ids, paginate=False)
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = "FAQ一覧"
        worksheet.append(["ID", "質問", "回答", *[labels.get(f"FAQ_TYPE_{i}", f"区分{i}") for i in range(1, 5)], "チャット利用", "更新日時"])
        jst = ZoneInfo("Asia/Tokyo")
        for row in rows:
            values = {item.classification_type.type_code: item.classification_value.value_name for item in row.classification_assignments}
            worksheet.append([
                row.id, row.question, row.answer, *[values.get(f"FAQ_TYPE_{i}", "") for i in range(1, 5)],
                "公開" if row.chat_enabled else "非公開", row.updated_at.astimezone(jst).strftime("%Y/%m/%d %H:%M"),
            ])
        output = BytesIO()
        workbook.save(output)
        return output.getvalue()
