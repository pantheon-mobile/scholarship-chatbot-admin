from datetime import datetime
import os

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, Response, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.repositories.data_source import DataSourceRepository
from app.schemas.data_source import (
    BulkDeleteRequest,
    BulkDeleteResponse,
    DataSourceFilters,
    DataSourceListResponse,
    DataSourceResponse,
    FileDataSourceUpdateRequest,
    FileUploadResponse,
    ToggleAnswerSourceRequest,
    ToggleReferenceLinkRequest,
    WebsiteDataSourceCreateRequest,
    WebsiteDataSourceUpdateRequest,
)
from app.services.data_source_service import (
    DataSourceNotFoundError,
    DataSourceService,
    DataSourceVersionConflictError,
    DataSourceUpdateError,
    FileUploadError,
    FileDataSourceRequiredError,
    ClassificationMismatchError,
    DataSourceCategoryNotFoundError,
    PageNotFoundError,
    WebsiteDataSourceCreateError,
    WebsiteDataSourceRequiredError,
    WebsiteDataSourceUpdateError,
)
from app.services.ingestion_launcher import launch_ingestion_worker
from app.storage import LocalStorage, S3Storage
from app.storage.base import StorageAdapter


router = APIRouter()


def get_ingestion_launcher():
    return launch_ingestion_worker


def get_service(session: AsyncSession = Depends(get_db)) -> DataSourceService:
    return DataSourceService(DataSourceRepository(session))


def get_storage() -> StorageAdapter:
    if os.getenv("STORAGE_BACKEND", "local").lower() == "s3":
        return S3Storage(
            os.getenv("INGESTION_S3_BUCKET", ""),
            os.getenv("INGESTION_ORIGINAL_PREFIX", "documents/admin/originals/"),
        )
    return LocalStorage()


def get_filters(
    keyword: str | None = None,
    format: str | None = None,
    status: str | None = None,
    category_id: int | None = None,
    type_1_value_id: int | None = None,
    type_2_value_id: int | None = None,
    type_3_value_id: int | None = None,
    answer_source_enabled: bool | None = None,
    priority: str | None = None,
    reference_link_visible: bool | None = None,
    sort: str = "updated_at",
    order: str = "desc",
    page: int = Query(default=1, ge=1),
    page_size: int = 10,
) -> DataSourceFilters:
    try:
        return DataSourceFilters(
            keyword=keyword, format=format, status=status, category_id=category_id,
            type_1_value_id=type_1_value_id, type_2_value_id=type_2_value_id, type_3_value_id=type_3_value_id,
            answer_source_enabled=answer_source_enabled, priority=priority,
            reference_link_visible=reference_link_visible, sort=sort, order=order,
            page=page, page_size=page_size,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/data-sources", response_model=DataSourceListResponse)
async def list_data_sources(filters: DataSourceFilters = Depends(get_filters), service: DataSourceService = Depends(get_service)):
    try:
        return await service.list(filters)
    except PageNotFoundError:
        raise HTTPException(status_code=422, detail={"code": "PAGE_NOT_FOUND", "message": "ページがありません。"}) from None


@router.get("/data-sources/export")
async def export_data_sources(filters: DataSourceFilters = Depends(get_filters), service: DataSourceService = Depends(get_service)):
    filters = filters.model_copy(update={"page": 1})
    data = await service.export_excel(filters)
    filename = f"datasource{datetime.now().strftime('%Y%m%d%H%M')}.xlsx"
    return StreamingResponse(
        iter([data]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.post("/data-sources/files", response_model=FileUploadResponse, status_code=201)
async def create_file_data_sources(
    files: list[UploadFile] = File(default=[]),
    title: str | None = Form(default=None),
    category_id: int | None = Form(default=None),
    type_1_value_id: int | None = Form(default=None),
    type_2_value_id: int | None = Form(default=None),
    type_3_value_id: int | None = Form(default=None),
    priority: str = Form(default="MEDIUM"),
    answer_source_enabled: bool = Form(default=True),
    reference_link_visible: bool = Form(default=True),
    service: DataSourceService = Depends(get_service),
    storage: StorageAdapter = Depends(get_storage),
):
    try:
        items = await service.create_file_sources(
            files,
            storage,
            title=title,
            category_id=category_id,
            type_1_value_id=type_1_value_id,
            type_2_value_id=type_2_value_id,
            type_3_value_id=type_3_value_id,
            priority=priority,
            answer_source_enabled=answer_source_enabled,
            reference_link_visible=reference_link_visible,
        )
        return FileUploadResponse(items=items, created_count=len(items))
    except FileUploadError as exc:
        status_code = 500 if exc.code == "FILE_SAVE_FAILED" else 422
        raise HTTPException(status_code=status_code, detail={"code": exc.code, "message": exc.message}) from None


@router.post("/data-sources/websites", response_model=DataSourceResponse, status_code=201)
async def create_website_data_source(
    payload: WebsiteDataSourceCreateRequest,
    service: DataSourceService = Depends(get_service),
):
    try:
        return await service.create_website_source(payload)
    except WebsiteDataSourceCreateError as exc:
        status_code = 500 if exc.code == "WEB_DATA_SOURCE_CREATE_FAILED" else 422
        raise HTTPException(status_code=status_code, detail={"code": exc.code, "message": exc.message}) from None


@router.post("/data-sources/ingestion/run-now", status_code=202)
async def run_ingestion_now(
    background_tasks: BackgroundTasks,
    launcher=Depends(get_ingestion_launcher),
):
    background_tasks.add_task(launcher)
    return {"message": "待機中のデータソースの処理を開始しました。"}


@router.get("/data-sources/{data_source_id}", response_model=DataSourceResponse)
async def get_data_source(data_source_id: int, service: DataSourceService = Depends(get_service)):
    try:
        return await service.get(data_source_id)
    except DataSourceNotFoundError:
        raise HTTPException(status_code=404, detail="指定されたデータソースが見つかりません。") from None


@router.put("/data-sources/{data_source_id}", response_model=DataSourceResponse)
async def update_file_data_source(
    data_source_id: int,
    payload: FileDataSourceUpdateRequest | WebsiteDataSourceUpdateRequest,
    service: DataSourceService = Depends(get_service),
):
    try:
        if isinstance(payload, WebsiteDataSourceUpdateRequest):
            return await service.update_website_attributes(data_source_id, payload)
        return await service.update_file_attributes(data_source_id, payload)
    except DataSourceNotFoundError:
        raise HTTPException(status_code=404, detail="指定されたデータソースが見つかりません。") from None
    except FileDataSourceRequiredError:
        raise HTTPException(status_code=422, detail={"code": "FILE_DATA_SOURCE_REQUIRED", "message": "ファイル編集の対象ではありません。"}) from None
    except ClassificationMismatchError as exc:
        raise HTTPException(status_code=422, detail={"code": "INVALID_CLASSIFICATION", "message": str(exc)}) from None
    except DataSourceCategoryNotFoundError:
        raise HTTPException(status_code=422, detail={"code": "CATEGORY_NOT_FOUND", "message": "指定されたカテゴリが存在しません。"}) from None
    except DataSourceVersionConflictError:
        raise HTTPException(status_code=409, detail={"code": "VERSION_CONFLICT", "message": "他の操作で情報が更新されています。再読み込みしてください。"}) from None
    except DataSourceUpdateError:
        raise HTTPException(status_code=500, detail={"code": "UPDATE_FAILED", "message": "データソースの更新に失敗しました。"}) from None
    except WebsiteDataSourceRequiredError:
        raise HTTPException(status_code=422, detail={"code": "WEB_DATA_SOURCE_REQUIRED", "message": "Webサイト編集の対象ではありません。"}) from None
    except WebsiteDataSourceUpdateError as exc:
        status_code = 500 if exc.code == "WEB_DATA_SOURCE_UPDATE_FAILED" else 422
        raise HTTPException(status_code=status_code, detail={"code": exc.code, "message": exc.message}) from None


@router.patch("/data-sources/{data_source_id}/answer-source", response_model=DataSourceResponse)
async def update_answer_source(data_source_id: int, payload: ToggleAnswerSourceRequest, service: DataSourceService = Depends(get_service)):
    try:
        return await service.update_answer_source(data_source_id, payload.enabled, payload.version)
    except DataSourceNotFoundError:
        raise HTTPException(status_code=404, detail="指定されたデータソースが見つかりません。") from None
    except DataSourceVersionConflictError:
        raise HTTPException(status_code=409, detail="更新前の情報と異なります。再度画面を更新してください。") from None


@router.patch("/data-sources/{data_source_id}/reference-link", response_model=DataSourceResponse)
async def update_reference_link(data_source_id: int, payload: ToggleReferenceLinkRequest, service: DataSourceService = Depends(get_service)):
    try:
        return await service.update_reference_link(data_source_id, payload.visible, payload.version)
    except DataSourceNotFoundError:
        raise HTTPException(status_code=404, detail="指定されたデータソースが見つかりません。") from None
    except DataSourceVersionConflictError:
        raise HTTPException(status_code=409, detail="更新前の情報と異なります。再度画面を更新してください。") from None


@router.delete("/data-sources/{data_source_id}")
async def delete_data_source(data_source_id: int, version: int = Query(..., ge=1), service: DataSourceService = Depends(get_service)):
    try:
        await service.delete(data_source_id, version)
        return Response(status_code=204)
    except DataSourceNotFoundError:
        raise HTTPException(status_code=404, detail="指定されたデータソースが見つかりません。") from None
    except DataSourceVersionConflictError:
        raise HTTPException(status_code=409, detail="削除前の情報と異なります。再度画面を更新してください。") from None


@router.post("/data-sources/bulk-delete", response_model=BulkDeleteResponse)
async def bulk_delete_data_sources(payload: BulkDeleteRequest, service: DataSourceService = Depends(get_service)):
    try:
        return BulkDeleteResponse(deleted_count=await service.bulk_delete(payload))
    except DataSourceNotFoundError:
        raise HTTPException(status_code=404, detail="削除対象に存在しないデータソースが含まれています。") from None
    except DataSourceVersionConflictError:
        raise HTTPException(status_code=409, detail="削除前の情報と異なります。再度画面を更新してください。") from None
