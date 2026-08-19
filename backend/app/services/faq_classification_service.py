from io import BytesIO

from openpyxl import Workbook
from sqlalchemy.exc import IntegrityError

from app.models.faq_classification import FaqClassificationType, FaqClassificationValue
from app.repositories.faq_classification import FaqClassificationRepository
from app.schemas.faq_classification import (
    FaqClassificationLabelUpdate,
    FaqClassificationOrderUpdate,
    FaqClassificationValueCreate,
    FaqClassificationValueUpdate,
)


class FaqClassificationError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class FaqClassificationService:
    def __init__(self, repository: FaqClassificationRepository) -> None:
        self.repository = repository

    async def list_types(self) -> list[FaqClassificationType]:
        return await self.repository.list_types()

    async def get_type(self, type_id: int) -> FaqClassificationType:
        row = await self.repository.get_type(type_id)
        if row is None:
            raise FaqClassificationError("FAQ_CLASSIFICATION_NOT_FOUND", "指定された区分が見つかりません。")
        return row

    @staticmethod
    def normalized(value: str, code: str, message: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise FaqClassificationError(code, message)
        return normalized

    async def update_label(self, type_id: int, payload: FaqClassificationLabelUpdate) -> FaqClassificationType:
        await self.get_type(type_id)
        label = self.normalized(payload.display_label, "FAQ_CLASSIFICATION_LABEL_REQUIRED", "区分ラベルを入力してください。")
        try:
            if not await self.repository.update_label(type_id, label, payload.version):
                raise FaqClassificationError("FAQ_CLASSIFICATION_VERSION_CONFLICT", "他の操作で情報が更新されています。再読み込みしてください。")
            await self.repository.commit()
            return await self.get_type(type_id)
        except FaqClassificationError:
            await self.repository.rollback()
            raise
        except Exception:
            await self.repository.rollback()
            raise

    async def add_value(self, type_id: int, payload: FaqClassificationValueCreate) -> FaqClassificationType:
        await self.get_type(type_id)
        name = self.normalized(payload.value_name, "FAQ_CLASSIFICATION_VALUE_REQUIRED", "区分値を入力してください。")
        if await self.repository.value_name_exists(type_id, name):
            raise FaqClassificationError("FAQ_CLASSIFICATION_VALUE_DUPLICATE", "同じ区分内に同じ値が既に存在します。")
        try:
            await self.repository.add_value(type_id, name)
            await self.repository.commit()
            return await self.get_type(type_id)
        except IntegrityError:
            await self.repository.rollback()
            raise FaqClassificationError("FAQ_CLASSIFICATION_VALUE_DUPLICATE", "同じ区分内に同じ値が既に存在します。") from None
        except Exception:
            await self.repository.rollback()
            raise

    async def _value_for_type(self, type_id: int, value_id: int) -> FaqClassificationValue:
        await self.get_type(type_id)
        value = await self.repository.get_value(value_id)
        if value is None or value.classification_type_id != type_id:
            raise FaqClassificationError("FAQ_CLASSIFICATION_VALUE_NOT_FOUND", "指定された区分値が見つかりません。")
        return value

    async def update_value(self, type_id: int, value_id: int, payload: FaqClassificationValueUpdate) -> FaqClassificationType:
        await self._value_for_type(type_id, value_id)
        name = self.normalized(payload.value_name, "FAQ_CLASSIFICATION_VALUE_REQUIRED", "区分値を入力してください。")
        if await self.repository.value_name_exists(type_id, name, exclude_id=value_id):
            raise FaqClassificationError("FAQ_CLASSIFICATION_VALUE_DUPLICATE", "同じ区分内に同じ値が既に存在します。")
        try:
            if not await self.repository.update_value(type_id, value_id, name, payload.version):
                raise FaqClassificationError("FAQ_CLASSIFICATION_VALUE_VERSION_CONFLICT", "他の操作で情報が更新されています。再読み込みしてください。")
            await self.repository.commit()
            return await self.get_type(type_id)
        except FaqClassificationError:
            await self.repository.rollback()
            raise
        except IntegrityError:
            await self.repository.rollback()
            raise FaqClassificationError("FAQ_CLASSIFICATION_VALUE_DUPLICATE", "同じ区分内に同じ値が既に存在します。") from None
        except Exception:
            await self.repository.rollback()
            raise

    async def delete_value(self, type_id: int, value_id: int, version: int) -> None:
        await self._value_for_type(type_id, value_id)
        try:
            if not await self.repository.delete_value(type_id, value_id, version):
                raise FaqClassificationError("FAQ_CLASSIFICATION_VALUE_VERSION_CONFLICT", "他の操作で情報が更新されています。再読み込みしてください。")
            await self.repository.commit()
        except FaqClassificationError:
            await self.repository.rollback()
            raise
        except Exception:
            await self.repository.rollback()
            raise

    async def reorder_values(self, type_id: int, payload: FaqClassificationOrderUpdate) -> FaqClassificationType:
        await self.get_type(type_id)
        try:
            result = await self.repository.reorder_values(type_id, payload.items)
            if result == "cross_type":
                raise FaqClassificationError("CROSS_FAQ_CLASSIFICATION_REORDER_NOT_ALLOWED", "異なる区分間では並び替えできません。")
            if result == "version_mismatch":
                raise FaqClassificationError("FAQ_CLASSIFICATION_VALUE_VERSION_CONFLICT", "他の操作で情報が更新されています。再読み込みしてください。")
            if result:
                raise FaqClassificationError("INVALID_FAQ_CLASSIFICATION_ORDER", "並び替えの入力が不正です。")
            await self.repository.commit()
            return await self.get_type(type_id)
        except FaqClassificationError:
            await self.repository.rollback()
            raise
        except Exception:
            await self.repository.rollback()
            raise

    async def export_excel(self) -> bytes:
        types = await self.repository.list_types()
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = "区分"
        worksheet.append(["区分", "区分タイトル名", "区分値"])
        for classification_type in types:
            if not classification_type.values:
                worksheet.append([classification_type.fixed_name, classification_type.display_label, ""])
            for value in classification_type.values:
                worksheet.append([classification_type.fixed_name, classification_type.display_label, value.value_name])
        output = BytesIO()
        workbook.save(output)
        return output.getvalue()
