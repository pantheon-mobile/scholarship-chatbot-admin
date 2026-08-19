from datetime import datetime
from io import BytesIO
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.repositories.faq_classification import FaqClassificationRepository
from app.schemas.faq_classification import (
    FaqClassificationLabelUpdate,
    FaqClassificationListResponse,
    FaqClassificationOrderUpdate,
    FaqClassificationTypeResponse,
    FaqClassificationValueCreate,
    FaqClassificationValueUpdate,
)
from app.services.faq_classification_service import FaqClassificationError, FaqClassificationService


router = APIRouter()


def get_service(session: AsyncSession = Depends(get_db)) -> FaqClassificationService:
    return FaqClassificationService(FaqClassificationRepository(session))


def api_error(error: FaqClassificationError) -> HTTPException:
    status = 409 if "VERSION_CONFLICT" in error.code else 404 if error.code.endswith("NOT_FOUND") else 422
    return HTTPException(status_code=status, detail={"code": error.code, "message": error.message})


@router.get("/faq-classifications", response_model=FaqClassificationListResponse)
async def list_faq_classifications(service: FaqClassificationService = Depends(get_service)):
    return FaqClassificationListResponse(items=await service.list_types())


@router.get("/faq-classifications/export")
async def export_faq_classifications(service: FaqClassificationService = Depends(get_service)):
    content = await service.export_excel()
    filename = f"classification{datetime.now(ZoneInfo('Asia/Tokyo')).strftime('%Y%m%d%H%M')}.xlsx"
    return StreamingResponse(
        BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.patch("/faq-classifications/{type_id}", response_model=FaqClassificationTypeResponse)
async def update_faq_classification_label(
    type_id: int,
    payload: FaqClassificationLabelUpdate,
    service: FaqClassificationService = Depends(get_service),
):
    try:
        return await service.update_label(type_id, payload)
    except FaqClassificationError as error:
        raise api_error(error) from None


@router.post("/faq-classifications/{type_id}/values", response_model=FaqClassificationTypeResponse, status_code=201)
async def create_faq_classification_value(
    type_id: int,
    payload: FaqClassificationValueCreate,
    service: FaqClassificationService = Depends(get_service),
):
    try:
        return await service.add_value(type_id, payload)
    except FaqClassificationError as error:
        raise api_error(error) from None


@router.put("/faq-classifications/{type_id}/values/{value_id}", response_model=FaqClassificationTypeResponse)
async def update_faq_classification_value(
    type_id: int,
    value_id: int,
    payload: FaqClassificationValueUpdate,
    service: FaqClassificationService = Depends(get_service),
):
    try:
        return await service.update_value(type_id, value_id, payload)
    except FaqClassificationError as error:
        raise api_error(error) from None


@router.delete("/faq-classifications/{type_id}/values/{value_id}", status_code=204)
async def delete_faq_classification_value(
    type_id: int,
    value_id: int,
    version: int = Query(..., ge=1),
    service: FaqClassificationService = Depends(get_service),
):
    try:
        await service.delete_value(type_id, value_id, version)
        return Response(status_code=204)
    except FaqClassificationError as error:
        raise api_error(error) from None


@router.patch("/faq-classifications/{type_id}/values/order", response_model=FaqClassificationTypeResponse)
async def reorder_faq_classification_values(
    type_id: int,
    payload: FaqClassificationOrderUpdate,
    service: FaqClassificationService = Depends(get_service),
):
    try:
        return await service.reorder_values(type_id, payload)
    except FaqClassificationError as error:
        raise api_error(error) from None
