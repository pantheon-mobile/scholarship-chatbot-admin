from io import BytesIO
from datetime import datetime

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.repositories.classification import ClassificationRepository
from app.schemas.classification import (
    ClassificationTypeResponse,
    ClassificationTypeUpdate,
    ClassificationValueCreate,
    ClassificationValueUpdate,
)
from app.services.classification_service import (
    ClassificationService,
    NotFoundError,
    DuplicateValueError,
    OptimisticLockError,
    InvalidOrderError,
)

router = APIRouter()


def get_service(session: AsyncSession = Depends(get_db)) -> ClassificationService:
    return ClassificationService(ClassificationRepository(session))


@router.get("/data-source-types", response_model=list[ClassificationTypeResponse])
async def list_data_source_types(service: ClassificationService = Depends(get_service)):
    return await service.list_types()


@router.get("/data-source-types/export")
async def export_data_source_types(service: ClassificationService = Depends(get_service)):
    excel_bytes = await service.export_excel()
    file_name = f"type{datetime.now().strftime('%Y%m%d%H%M')}.xlsx"
    return StreamingResponse(
        BytesIO(excel_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={file_name}"},
    )


@router.patch("/data-source-types/{type_id}", response_model=ClassificationTypeResponse)
async def update_type_label(
    type_id: int,
    payload: ClassificationTypeUpdate,
    service: ClassificationService = Depends(get_service),
):
    try:
        return await service.update_type_label(type_id, payload)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="指定された種別が見つかりません。")
    except OptimisticLockError:
        raise HTTPException(status_code=409, detail="更新前の情報と異なります。再度画面を更新してください。")


@router.post("/data-source-types/{type_id}/values", response_model=ClassificationTypeResponse)
async def create_data_source_value(
    type_id: int,
    payload: ClassificationValueCreate,
    service: ClassificationService = Depends(get_service),
):
    try:
        return await service.add_value(type_id, payload)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="指定された種別が見つかりません。")
    except DuplicateValueError:
        raise HTTPException(status_code=422, detail="同じ種別内に同じ値が既に存在します。")


@router.patch("/data-source-types/{type_id}/values/{value_id}", response_model=ClassificationTypeResponse)
async def update_data_source_value(
    type_id: int,
    value_id: int,
    payload: ClassificationValueUpdate,
    service: ClassificationService = Depends(get_service),
):
    try:
        return await service.update_value(type_id, value_id, payload)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="指定された種別または値が見つかりません。")
    except DuplicateValueError:
        raise HTTPException(status_code=422, detail="同じ種別内に同じ値が既に存在します。")
    except OptimisticLockError:
        raise HTTPException(status_code=409, detail="更新前の情報と異なります。再度画面を更新してください。")


@router.delete("/data-source-types/{type_id}/values/{value_id}")
async def delete_data_source_value(
    type_id: int,
    value_id: int,
    version: int = Query(...),
    service: ClassificationService = Depends(get_service),
):
    try:
        await service.delete_value(type_id, value_id, version)
        return Response(status_code=204)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="指定された種別または値が見つかりません。")
    except OptimisticLockError:
        raise HTTPException(status_code=409, detail="削除前の情報と異なります。再度画面を更新してください。")


@router.put("/data-source-types/{type_id}/values/order")
async def reorder_data_source_values(
    type_id: int,
    ordered_ids: list[int] = Body(...),
    service: ClassificationService = Depends(get_service),
):
    try:
        await service.reorder_values(type_id, ordered_ids)
        return Response(status_code=204)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="指定された種別が見つかりません。")
    except InvalidOrderError:
        raise HTTPException(status_code=422, detail="並び替えの入力が不正です。")

