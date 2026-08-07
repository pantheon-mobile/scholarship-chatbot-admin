from __future__ import annotations

from io import BytesIO
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from fastapi import UploadFile
from openpyxl import Workbook

from app.models.data_source import DataSource
from app.repositories.data_source import DataSourceRepository
from app.schemas.data_source import (
    BulkDeleteRequest,
    ClassificationAssignment,
    DataSourceClassificationResponse,
    DataSourceFileResponse,
    DataSourceFilters,
    DataSourceListResponse,
    DataSourceResponse,
    DataSourceWebsiteResponse,
    FileDataSourceUpdateRequest,
    WebsiteDataSourceCreateRequest,
)
from app.services.file_upload_validation import FileUploadValidationError, validate_uploads
from app.storage.base import StorageAdapter


class DataSourceNotFoundError(Exception):
    pass


class DataSourceVersionConflictError(Exception):
    pass


class PageNotFoundError(Exception):
    pass


class ClassificationMismatchError(Exception):
    pass


class FileDataSourceRequiredError(Exception):
    pass


class DataSourceUpdateError(Exception):
    pass


class WebsiteDataSourceCreateError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class FileUploadError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class DataSourceService:
    def __init__(self, repository: DataSourceRepository) -> None:
        self.repository = repository

    @staticmethod
    def serialize(row: DataSource) -> DataSourceResponse:
        classifications = sorted(row.classification_links, key=lambda link: link.classification_type.display_order)
        return DataSourceResponse(
            id=row.id,
            source_type=row.source_type,
            title=row.title,
            format=row.format,
            status=row.status,
            category_name=row.category_name,
            size_bytes=row.size_bytes,
            character_count=row.character_count,
            answer_source_enabled=row.answer_source_enabled,
            priority=row.priority,
            reference_link_visible=row.reference_link_visible,
            updated_at=row.updated_at,
            version=row.version,
            file=DataSourceFileResponse(file_name=row.file.file_name) if row.file else None,
            website=DataSourceWebsiteResponse(url=row.website.url) if row.website else None,
            classifications=[DataSourceClassificationResponse(
                type_code=link.classification_type.type_code,
                classification_type_id=link.classification_type_id,
                classification_value_id=link.classification_value_id,
                display_label=link.classification_type.display_label,
                value_name=link.classification_value.value_name,
            ) for link in classifications],
        )

    async def list(self, filters: DataSourceFilters) -> DataSourceListResponse:
        rows, total_count, total_pages, total_size = await self.repository.list(filters)
        if filters.page > 1 and filters.page > total_pages:
            raise PageNotFoundError()
        return DataSourceListResponse(
            items=[self.serialize(row) for row in rows],
            page=filters.page,
            page_size=filters.page_size,
            total_count=total_count,
            total_pages=total_pages,
            total_size_bytes=total_size,
            sort=filters.sort,
            order=filters.order,
        )

    async def _get(self, data_source_id: int) -> DataSource:
        row = await self.repository.get(data_source_id)
        if row is None:
            raise DataSourceNotFoundError()
        return row

    async def get(self, data_source_id: int) -> DataSourceResponse:
        return self.serialize(await self._get(data_source_id))

    async def update_file_attributes(
        self,
        data_source_id: int,
        payload: FileDataSourceUpdateRequest,
    ) -> DataSourceResponse:
        row = await self._get(data_source_id)
        if row.source_type != "FILE" or row.file is None:
            raise FileDataSourceRequiredError()

        title = payload.title.strip() or row.file.file_name
        classifications: list[tuple[int, int]] = []
        for type_code, value_id in (
            ("TYPE_1", payload.type_1_value_id),
            ("TYPE_2", payload.type_2_value_id),
            ("TYPE_3", payload.type_3_value_id),
        ):
            if value_id is None:
                continue
            pair = await self.repository.resolve_classification_value(type_code, value_id)
            if pair is None:
                raise ClassificationMismatchError("種別値と種別の組み合わせが不正です。")
            classifications.append(pair)

        try:
            updated = await self.repository.update_file_attributes(
                data_source_id, payload, title, classifications
            )
        except Exception as exc:
            await self.repository.rollback()
            raise DataSourceUpdateError() from exc
        if not updated:
            raise DataSourceVersionConflictError()
        return self.serialize(await self._get(data_source_id))

    async def create_website_source(
        self,
        payload: WebsiteDataSourceCreateRequest,
    ) -> DataSourceResponse:
        url = payload.url.strip()
        if not url:
            raise WebsiteDataSourceCreateError("URL_REQUIRED", "URLを入力してください。")
        if len(url) > 500 or any(character.isspace() for character in url):
            raise WebsiteDataSourceCreateError("INVALID_URL", "正しいURLを入力してください。")
        try:
            parsed = urlsplit(url)
            valid_url = parsed.scheme.lower() in {"http", "https"} and bool(parsed.netloc) and bool(parsed.hostname)
            parsed.port
        except ValueError:
            valid_url = False
        if not valid_url:
            raise WebsiteDataSourceCreateError("INVALID_URL", "正しいURLを入力してください。")

        title = payload.title.strip() or url
        if len(title) > 500:
            raise WebsiteDataSourceCreateError("TITLE_TOO_LONG", "タイトルが長すぎます。")
        if payload.priority not in {"HIGH", "MEDIUM", "LOW"}:
            raise WebsiteDataSourceCreateError("INVALID_PRIORITY", "回答利用の優先度が不正です。")

        classifications: list[tuple[int, int]] = []
        for type_code, value_id in (
            ("TYPE_1", payload.type_1_value_id),
            ("TYPE_2", payload.type_2_value_id),
            ("TYPE_3", payload.type_3_value_id),
        ):
            if value_id is None:
                continue
            pair = await self.repository.resolve_classification_value(type_code, value_id)
            if pair is None:
                raise WebsiteDataSourceCreateError("INVALID_CLASSIFICATION", "種別値と種別の組み合わせが不正です。")
            classifications.append(pair)

        try:
            data_source_id = await self.repository.create_website_source(
                url=url,
                title=title,
                priority=payload.priority,
                answer_source_enabled=payload.answer_source_enabled,
                reference_link_visible=payload.reference_link_visible,
                classifications=classifications,
            )
            await self.repository.commit()
        except Exception as exc:
            await self.repository.rollback()
            raise WebsiteDataSourceCreateError("WEB_DATA_SOURCE_CREATE_FAILED", "Webサイトの追加に失敗しました。") from exc
        return self.serialize(await self._get(data_source_id))

    async def update_answer_source(self, data_source_id: int, enabled: bool, version: int) -> DataSourceResponse:
        await self._get(data_source_id)
        if not await self.repository.update_toggle(data_source_id, "answer_source_enabled", enabled, version):
            raise DataSourceVersionConflictError()
        return self.serialize(await self._get(data_source_id))

    async def update_reference_link(self, data_source_id: int, visible: bool, version: int) -> DataSourceResponse:
        await self._get(data_source_id)
        if not await self.repository.update_toggle(data_source_id, "reference_link_visible", visible, version):
            raise DataSourceVersionConflictError()
        return self.serialize(await self._get(data_source_id))

    async def delete(self, data_source_id: int, version: int) -> None:
        await self._get(data_source_id)
        if not await self.repository.delete_one(data_source_id, version):
            raise DataSourceVersionConflictError()

    async def bulk_delete(self, payload: BulkDeleteRequest) -> int:
        try:
            return await self.repository.bulk_delete(payload.items)
        except LookupError as exc:
            raise DataSourceNotFoundError() from exc
        except ValueError as exc:
            if str(exc) == "version_mismatch":
                raise DataSourceVersionConflictError() from exc
            raise

    async def validate_classification_assignments(self, assignments: list[ClassificationAssignment]) -> None:
        seen_types: set[int] = set()
        for assignment in assignments:
            if assignment.classification_type_id in seen_types:
                raise ClassificationMismatchError("同じ種別を複数指定できません。")
            seen_types.add(assignment.classification_type_id)
            if not await self.repository.classification_value_matches_type(
                assignment.classification_type_id,
                assignment.classification_value_id,
            ):
                raise ClassificationMismatchError("種別値と種別の組み合わせが不正です。")

    async def create_file_sources(
        self,
        files: list[UploadFile],
        storage: StorageAdapter,
        *,
        title: str | None,
        type_1_value_id: int | None,
        type_2_value_id: int | None,
        type_3_value_id: int | None,
        priority: str,
        answer_source_enabled: bool,
        reference_link_visible: bool,
    ) -> list[DataSourceResponse]:
        try:
            validated = validate_uploads(files)
        except FileUploadValidationError as exc:
            raise FileUploadError(exc.code, exc.message) from exc

        normalized_title = (title or "").strip()
        if len(validated) > 1 and normalized_title:
            raise FileUploadError("TITLE_NOT_ALLOWED", "複数ファイルを選択した場合はタイトルを指定できません。")
        if len(normalized_title) > 500:
            raise FileUploadError("INVALID_TITLE", "タイトルは500文字以内で入力してください。")
        if priority not in {"HIGH", "MEDIUM", "LOW"}:
            raise FileUploadError("INVALID_PRIORITY", "回答利用の優先度が不正です。")

        classification_pairs: list[tuple[int, int]] = []
        for type_code, value_id in (
            ("TYPE_1", type_1_value_id),
            ("TYPE_2", type_2_value_id),
            ("TYPE_3", type_3_value_id),
        ):
            if value_id is None:
                continue
            pair = await self.repository.resolve_classification_value(type_code, value_id)
            if pair is None:
                raise FileUploadError("INVALID_CLASSIFICATION", "種別値と種別の組み合わせが不正です。")
            classification_pairs.append(pair)

        staged: list[tuple[Path, str]] = []
        finalized_keys: list[str] = []
        records: list[dict] = []
        try:
            for item in validated:
                storage_key = storage.create_storage_key(item.extension)
                temporary_path = storage.save_temporary(item.upload.file)
                staged.append((temporary_path, storage_key))
                records.append({
                    "title": normalized_title if len(validated) == 1 and normalized_title else item.file_name,
                    "file_name": item.file_name,
                    "storage_key": storage_key,
                    "extension": item.extension,
                    "size_bytes": item.size_bytes,
                    "content_type": item.content_type,
                })

            ids = await self.repository.create_file_sources(
                records,
                priority=priority,
                answer_source_enabled=answer_source_enabled,
                reference_link_visible=reference_link_visible,
                classifications=classification_pairs,
            )
            for temporary_path, storage_key in staged:
                storage.finalize(temporary_path, storage_key)
                finalized_keys.append(storage_key)
            await self.repository.commit()
        except Exception as exc:
            await self.repository.rollback()
            for temporary_path, _ in staged:
                storage.delete_temporary(temporary_path)
            for storage_key in finalized_keys:
                storage.delete(storage_key)
            if isinstance(exc, FileUploadError):
                raise
            raise FileUploadError("FILE_SAVE_FAILED", "ファイルの追加に失敗しました。") from exc

        result: list[DataSourceResponse] = []
        for data_source_id in ids:
            result.append(self.serialize(await self._get(data_source_id)))
        return result

    async def export_excel(self, filters: DataSourceFilters) -> bytes:
        export_filters = filters.model_copy(update={"page": 1, "page_size": 100})
        all_rows: list[DataSourceResponse] = []
        while True:
            result = await self.list(export_filters)
            all_rows.extend(result.items)
            if export_filters.page >= result.total_pages:
                break
            export_filters = export_filters.model_copy(update={"page": export_filters.page + 1})

        source_labels = {"FILE": "ファイル", "WEB": "Web"}
        status_labels = {"PREPARING": "準備中", "TRAINING": "学習中", "AVAILABLE": "利用可", "ERROR": "エラー"}
        priority_labels = {"HIGH": "高", "MEDIUM": "中", "LOW": "低"}
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = "データソース一覧"
        worksheet.append(["ID", "種類", "タイトル", "ファイル名／URL", "形式", "状態", "カテゴリ", "種別1", "種別2", "種別3", "サイズ", "文字数", "回答ソース", "優先度", "参照リンク", "更新日時"])
        for row in all_rows:
            values = {item.type_code: item.value_name for item in row.classifications}
            location = row.file.file_name if row.file else row.website.url if row.website else ""
            updated = row.updated_at.astimezone(ZoneInfo("Asia/Tokyo")).strftime("%Y/%m/%d %H:%M")
            worksheet.append([
                row.id, source_labels[row.source_type], row.title, location, row.format,
                status_labels[row.status], row.category_name or "", values.get("TYPE_1", ""),
                values.get("TYPE_2", ""), values.get("TYPE_3", ""), row.size_bytes,
                row.character_count, "有効" if row.answer_source_enabled else "無効",
                priority_labels[row.priority], "表示" if row.reference_link_visible else "非表示", updated,
            ])
        output = BytesIO()
        workbook.save(output)
        return output.getvalue()
