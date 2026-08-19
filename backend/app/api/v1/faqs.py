from datetime import datetime
from io import BytesIO
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.repositories.faq import FaqRepository
from app.schemas.faq import (
    FaqBulkDeleteRequest,
    FaqBulkDeleteResponse,
    FaqCreateRequest,
    FaqDetailResponse,
    FaqFilters,
    FaqListResponse,
    FaqImportResponse,
    FaqUpdateRequest,
)
from app.services.faq_service import FaqError, FaqService

router = APIRouter()


def get_service(session: AsyncSession = Depends(get_db)) -> FaqService:
    return FaqService(FaqRepository(session))


def api_error(error: FaqError) -> HTTPException:
    status = 500 if error.code in ("FAQ_UPDATE_FAILED", "FAQ_IMPORT_FAILED") else 409 if error.code == "FAQ_VERSION_CONFLICT" else 404 if error.code == "FAQ_NOT_FOUND" else 422
    detail = {"code": error.code, "message": error.message}
    if error.errors is not None:
        detail["errors"] = [item.model_dump() for item in error.errors]
    return HTTPException(status_code=status, detail=detail)


@router.get("/faqs", response_model=FaqListResponse)
async def list_faqs(filters: FaqFilters = Depends(), service: FaqService = Depends(get_service)):
    try:
        return await service.list(filters)
    except FaqError as error:
        raise api_error(error) from None


@router.post("/faqs", response_model=FaqDetailResponse, status_code=201)
async def create_faq(payload: FaqCreateRequest, service: FaqService = Depends(get_service)):
    try:
        return await service.create(payload)
    except FaqError as error:
        raise api_error(error) from None


@router.get("/faqs/export")
async def export_faqs(filters: FaqFilters = Depends(), service: FaqService = Depends(get_service)):
    try:
        labels = await service.repository.list_type_labels()
        content = await service.export_excel(filters, labels)
    except FaqError as error:
        raise api_error(error) from None
    filename = f"faq{datetime.now(ZoneInfo('Asia/Tokyo')).strftime('%Y%m%d%H%M')}.xlsx"
    return StreamingResponse(
        BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/faqs/import-template")
async def download_faq_import_template(service: FaqService = Depends(get_service)):
    content = await service.create_import_template()
    return StreamingResponse(
        BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=faq_import_template.xlsx"},
    )


@router.post("/faqs/import", response_model=FaqImportResponse)
async def import_faqs(file: UploadFile = File(...), service: FaqService = Depends(get_service)):
    try:
        return await service.import_excel(file)
    except FaqError as error:
        raise api_error(error) from None


@router.post("/faqs/bulk-delete", response_model=FaqBulkDeleteResponse)
async def bulk_delete_faqs(payload: FaqBulkDeleteRequest, service: FaqService = Depends(get_service)):
    try:
        return FaqBulkDeleteResponse(deleted_count=await service.bulk_delete(payload))
    except FaqError as error:
        raise api_error(error) from None


@router.get("/faqs/{faq_id}", response_model=FaqDetailResponse)
async def get_faq(faq_id: int, service: FaqService = Depends(get_service)):
    try:
        return await service.get_detail(faq_id)
    except FaqError as error:
        raise api_error(error) from None


@router.put("/faqs/{faq_id}", response_model=FaqDetailResponse)
async def update_faq(faq_id: int, payload: FaqUpdateRequest, service: FaqService = Depends(get_service)):
    try:
        return await service.update(faq_id, payload)
    except FaqError as error:
        raise api_error(error) from None


@router.delete("/faqs/{faq_id}", status_code=204)
async def delete_faq(
    faq_id: int,
    version: int = Query(..., ge=1),
    service: FaqService = Depends(get_service),
):
    try:
        await service.delete(faq_id, version)
        return Response(status_code=204)
    except FaqError as error:
        raise api_error(error) from None
