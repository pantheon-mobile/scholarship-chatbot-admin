from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.repositories.dashboard import DashboardRepository
from app.schemas.dashboard import DashboardResponse
from app.services.dashboard_service import DashboardError, DashboardService


router = APIRouter(tags=["dashboard"])


def get_service(session: AsyncSession = Depends(get_db)) -> DashboardService:
    return DashboardService(DashboardRepository(session))


@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(
    from_date: date = Query(..., alias="from"),
    to_date: date = Query(..., alias="to"),
    service: DashboardService = Depends(get_service),
):
    try:
        return await service.get(from_date, to_date)
    except DashboardError as error:
        raise HTTPException(
            status_code=422,
            detail={"code": error.code, "message": error.message},
        ) from None
