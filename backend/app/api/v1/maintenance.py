import os

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import require_system_admin_session
from app.core.db import get_db
from app.services.ingestion_processor import AwsIngestionProcessor, LocalDataSourceCleanupProcessor
from app.services.maintenance_service import (
    MaintenanceCleanupError,
    MaintenanceDisabledError,
    MaintenanceService,
    destructive_purge_enabled,
)

router = APIRouter(prefix="/maintenance", tags=["maintenance"])


def get_service(session: AsyncSession = Depends(get_db)) -> MaintenanceService:
    cleanup = AwsIngestionProcessor() if os.getenv("INGESTION_S3_BUCKET", "").strip() else LocalDataSourceCleanupProcessor()
    return MaintenanceService(session, cleanup)


@router.get("/capabilities", dependencies=[Depends(require_system_admin_session)])
async def capabilities():
    return {"bulk_purge_enabled": destructive_purge_enabled()}


@router.post("/purge", dependencies=[Depends(require_system_admin_session)])
async def purge(service: MaintenanceService = Depends(get_service)):
    try:
        return await service.purge()
    except MaintenanceDisabledError:
        raise HTTPException(status_code=404, detail="この環境では一括消去を利用できません。") from None
    except MaintenanceCleanupError:
        raise HTTPException(status_code=502, detail="S3またはKnowledge Baseの消去・同期に失敗したため、DBは消去していません。") from None
