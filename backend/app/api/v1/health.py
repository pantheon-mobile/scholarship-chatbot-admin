from fastapi import APIRouter
from sqlalchemy import text

from app.core.db import engine

router = APIRouter()

@router.get("/health")
async def health_check() -> dict[str, str]:
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    return {"status": "ok"}
