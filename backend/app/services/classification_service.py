from io import BytesIO
from typing import List

from openpyxl import Workbook
from sqlalchemy.exc import IntegrityError

from app.models.classification import ClassificationType
from app.repositories.classification import ClassificationRepository
from app.schemas.classification import (
    ClassificationTypeUpdate,
    ClassificationValueCreate,
    ClassificationValueUpdate,
)


class NotFoundError(Exception):
    pass


class DuplicateValueError(Exception):
    pass


class OptimisticLockError(Exception):
    pass


class InvalidOrderError(Exception):
    pass


class ClassificationService:
    def __init__(self, repository: ClassificationRepository) -> None:
        self.repository = repository

    async def list_types(self) -> List[ClassificationType]:
        return await self.repository.list_types()

    async def get_type(self, type_id: int) -> ClassificationType:
        classification_type = await self.repository.get_type(type_id)
        if classification_type is None:
            raise NotFoundError("classification type not found")
        return classification_type

    async def update_type_label(self, type_id: int, payload: ClassificationTypeUpdate) -> ClassificationType:
        await self.get_type(type_id)
        try:
            return await self.repository.update_type_label(type_id, payload.display_label, payload.version)
        except ValueError as exc:
            if str(exc) == "version_mismatch":
                raise OptimisticLockError("version mismatch")
            raise

    async def add_value(self, type_id: int, payload: ClassificationValueCreate) -> ClassificationType:
        await self.get_type(type_id)
        if await self.repository.value_name_exists(type_id, payload.value_name):
            raise DuplicateValueError("duplicate value name")
        try:
            await self.repository.add_value(type_id, payload.value_name)
            return await self.get_type(type_id)
        except IntegrityError:
            await self.repository.session.rollback()
            raise DuplicateValueError("duplicate value name")

    async def update_value(self, type_id: int, value_id: int, payload: ClassificationValueUpdate) -> ClassificationType:
        await self.get_type(type_id)
        value = await self.repository.get_value(value_id, type_id)
        if value is None:
            raise NotFoundError("classification value not found")
        if await self.repository.value_name_exists(type_id, payload.value_name, exclude_id=value_id):
            raise DuplicateValueError("duplicate value name")
        try:
            await self.repository.update_value(value_id, type_id, payload.value_name, payload.version)
            return await self.get_type(type_id)
        except ValueError as exc:
            if str(exc) == "version_mismatch":
                raise OptimisticLockError("version mismatch")
            raise

    async def delete_value(self, type_id: int, value_id: int, version: int) -> ClassificationType:
        await self.get_type(type_id)
        value = await self.repository.get_value(value_id, type_id)
        if value is None:
            raise NotFoundError("classification value not found")
        try:
            await self.repository.delete_value(value_id, type_id, version)
            return await self.get_type(type_id)
        except ValueError as exc:
            if str(exc) == "version_mismatch":
                raise OptimisticLockError("version mismatch")
            raise

    async def reorder_values(self, type_id: int, ordered_ids: List[int]) -> ClassificationType:
        await self.get_type(type_id)
        try:
            await self.repository.reorder_values(type_id, ordered_ids)
            return await self.get_type(type_id)
        except ValueError as exc:
            if str(exc) == "invalid_order":
                raise InvalidOrderError("invalid order payload")
            raise

    async def export_excel(self) -> bytes:
        types = await self.repository.list_types()
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = "種別"
        worksheet.append(["種別", "種別タイトル名", "種別値"])
        for classification_type in types:
            for value in classification_type.values:
                worksheet.append([
                    classification_type.fixed_name,
                    classification_type.display_label,
                    value.value_name,
                ])
        output = BytesIO()
        workbook.save(output)
        return output.getvalue()
