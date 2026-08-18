from datetime import datetime
from io import BytesIO
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.repositories.category import CategoryRepository
from app.schemas.category import CategoryBulkDeleteRequest, CategoryBulkDeleteResponse, CategoryCreateRequest, CategoryListResponse, CategoryOrderRequest, CategoryResponse, CategoryUpdateRequest
from app.services.category_service import (
    CategoryNotFoundError,
    CategoryCycleError,
    CategoryNameRequiredError,
    CategoryNameTooLongError,
    CategoryService,
    CategoryVersionConflictError,
    CrossParentReorderError,
    DuplicateCategoryNameError,
    EmptyCategorySelectionError,
    InvalidCategoryOrderError,
    ParentCategoryNotFoundError,
)

router = APIRouter()


def get_service(session: AsyncSession = Depends(get_db)) -> CategoryService:
    return CategoryService(CategoryRepository(session))


def error(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


@router.get("/categories", response_model=CategoryListResponse)
async def list_categories(service: CategoryService = Depends(get_service)):
    return {"items": await service.list_categories()}


def raise_write_error(exc: Exception) -> None:
    if isinstance(exc, CategoryNameRequiredError):
        raise HTTPException(status_code=422, detail=error("CATEGORY_NAME_REQUIRED", "カテゴリが入力されていません"))
    if isinstance(exc, CategoryNameTooLongError):
        raise HTTPException(status_code=422, detail=error("CATEGORY_NAME_TOO_LONG", "カテゴリは15文字以内で入力してください。"))
    if isinstance(exc, ParentCategoryNotFoundError):
        raise HTTPException(status_code=422, detail=error("PARENT_CATEGORY_NOT_FOUND", "親カテゴリが見つかりません。"))
    if isinstance(exc, DuplicateCategoryNameError):
        raise HTTPException(status_code=422, detail=error("CATEGORY_NAME_DUPLICATE", "同じ親カテゴリ内に同名のカテゴリがあります。"))
    if isinstance(exc, CategoryCycleError):
        raise HTTPException(status_code=422, detail=error("CATEGORY_CYCLE_NOT_ALLOWED", "自分自身または子孫を親カテゴリには指定できません。"))
    if isinstance(exc, CategoryNotFoundError):
        raise HTTPException(status_code=404, detail=error("CATEGORY_NOT_FOUND", "カテゴリが見つかりません。"))
    if isinstance(exc, CategoryVersionConflictError):
        raise HTTPException(status_code=409, detail=error("CATEGORY_VERSION_CONFLICT", "他の操作で情報が更新されています。再読み込みしてください。"))
    raise exc


@router.post("/categories", response_model=CategoryResponse, status_code=201)
async def create_category(payload: CategoryCreateRequest, service: CategoryService = Depends(get_service)):
    try:
        return await service.create(payload)
    except (CategoryNameRequiredError, CategoryNameTooLongError, ParentCategoryNotFoundError, DuplicateCategoryNameError) as exc:
        raise_write_error(exc)


@router.get("/categories/export")
async def export_categories(service: CategoryService = Depends(get_service)):
    content = await service.export_excel()
    file_name = f"category{datetime.now(ZoneInfo('Asia/Tokyo')).strftime('%Y%m%d%H%M')}.xlsx"
    return StreamingResponse(
        BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={file_name}"},
    )


@router.post("/categories/bulk-delete", response_model=CategoryBulkDeleteResponse)
async def bulk_delete_categories(payload: CategoryBulkDeleteRequest, service: CategoryService = Depends(get_service)):
    if not payload.items:
        raise HTTPException(status_code=422, detail=error("EMPTY_CATEGORY_SELECTION", "削除するカテゴリを選択してください。"))
    try:
        return {"deleted_count": await service.bulk_delete(payload.items)}
    except EmptyCategorySelectionError:
        raise HTTPException(status_code=422, detail=error("EMPTY_CATEGORY_SELECTION", "削除するカテゴリを選択してください。"))
    except CategoryNotFoundError:
        raise HTTPException(status_code=404, detail=error("CATEGORY_NOT_FOUND", "カテゴリが見つかりません。"))
    except CategoryVersionConflictError:
        raise HTTPException(status_code=409, detail=error("CATEGORY_VERSION_CONFLICT", "他の操作で情報が更新されています。再読み込みしてください。"))


@router.patch("/categories/order", response_model=list[CategoryResponse])
async def reorder_categories(payload: CategoryOrderRequest, service: CategoryService = Depends(get_service)):
    try:
        return await service.reorder(payload)
    except CrossParentReorderError:
        raise HTTPException(status_code=422, detail=error("CROSS_PARENT_REORDER_NOT_ALLOWED", "異なる親カテゴリ間では並び替えできません。"))
    except InvalidCategoryOrderError:
        raise HTTPException(status_code=422, detail=error("INVALID_CATEGORY_ORDER", "並び替えの入力が不正です。"))
    except CategoryVersionConflictError:
        raise HTTPException(status_code=409, detail=error("CATEGORY_VERSION_CONFLICT", "他の操作で情報が更新されています。再読み込みしてください。"))


@router.put("/categories/{category_id}", response_model=CategoryResponse)
async def update_category(category_id: int, payload: CategoryUpdateRequest, service: CategoryService = Depends(get_service)):
    try:
        return await service.update(category_id, payload)
    except (
        CategoryNameRequiredError,
        CategoryNameTooLongError,
        ParentCategoryNotFoundError,
        DuplicateCategoryNameError,
        CategoryCycleError,
        CategoryNotFoundError,
        CategoryVersionConflictError,
    ) as exc:
        raise_write_error(exc)


@router.delete("/categories/{category_id}")
async def delete_category(category_id: int, version: int = Query(..., ge=1), service: CategoryService = Depends(get_service)):
    try:
        await service.delete(category_id, version)
        return Response(status_code=204)
    except CategoryNotFoundError:
        raise HTTPException(status_code=404, detail=error("CATEGORY_NOT_FOUND", "カテゴリが見つかりません。"))
    except CategoryVersionConflictError:
        raise HTTPException(status_code=409, detail=error("CATEGORY_VERSION_CONFLICT", "他の操作で情報が更新されています。再読み込みしてください。"))
