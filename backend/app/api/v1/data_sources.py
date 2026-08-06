from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response
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
    ToggleAnswerSourceRequest,
    ToggleReferenceLinkRequest,
)
from app.services.data_source_service import (
    DataSourceNotFoundError,
    DataSourceService,
    DataSourceVersionConflictError,
    PageNotFoundError,
)


router = APIRouter()


def get_service(session: AsyncSession = Depends(get_db)) -> DataSourceService:
    return DataSourceService(DataSourceRepository(session))


def get_filters(
    keyword: str | None = None,
    format: str | None = None,
    status: str | None = None,
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
            keyword=keyword, format=format, status=status,
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
