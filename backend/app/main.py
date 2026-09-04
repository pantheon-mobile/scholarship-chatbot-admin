import os
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.health import router as health_router
from app.api.v1.data_source_types import router as data_source_router
from app.api.v1.data_sources import router as data_sources_router
from app.api.v1.categories import router as categories_router
from app.api.v1.faq_classifications import router as faq_classifications_router
from app.api.v1.faqs import router as faqs_router
from app.api.v1.analytics import router as analytics_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.auth import router as auth_router
from app.api.v1.auth import require_authenticated_session, require_system_admin_session
from app.api.v1.chat import router as chat_router
from app.api.v1.reporting import router as reporting_router
from app.core.db import SessionLocal
from app.models.auth import AdminOperationLog
from app.repositories.reporting import ReportingRepository
from app.services.analytics_service import AnalyticsService

app = FastAPI(title="Scholarship Chatbot Admin Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip() for origin in os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:3000").split(",")
        if origin.strip()
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


def _is_audited_operation(request: Request) -> bool:
    path = request.url.path
    if not path.startswith("/api/v1/"):
        return False
    if path.startswith(("/api/v1/auth/", "/api/v1/analytics/", "/api/v1/chat/")):
        return False
    return request.method in {"POST", "PUT", "PATCH", "DELETE"} or path.endswith(".csv")


@app.middleware("http")
async def record_admin_operation(request: Request, call_next):
    response = await call_next(request)
    current = getattr(request.state, "auth_session", None)
    if current is not None and _is_audited_operation(request):
        try:
            async with SessionLocal() as session:
                operator_key = AnalyticsService(ReportingRepository(session)).visitor_key(
                    "AUTHENTICATED", f"{current.site}:{current.subject}"
                )
                session.add(AdminOperationLog(
                    id=uuid4(),
                    operator_key=operator_key,
                    operator_subject=current.subject,
                    operator_display_name=current.display_name,
                    operator_role=current.role,
                    operator_site=current.site,
                    http_method=request.method,
                    request_path=request.url.path,
                    status_code=response.status_code,
                    operated_at=datetime.now(timezone.utc),
                ))
                await session.commit()
        except Exception:
            # 操作ログ障害で本来の管理操作を失敗させない。
            pass
    return response

app.include_router(health_router, prefix="/api/v1")
admin_dependencies = [Depends(require_authenticated_session)]
system_admin_dependencies = [Depends(require_system_admin_session)]
app.include_router(data_source_router, prefix="/api/v1", dependencies=system_admin_dependencies)
app.include_router(data_sources_router, prefix="/api/v1", dependencies=system_admin_dependencies)
app.include_router(categories_router, prefix="/api/v1", dependencies=system_admin_dependencies)
app.include_router(faq_classifications_router, prefix="/api/v1", dependencies=admin_dependencies)
app.include_router(faqs_router, prefix="/api/v1", dependencies=admin_dependencies)
app.include_router(analytics_router, prefix="/api/v1", dependencies=admin_dependencies)
app.include_router(dashboard_router, prefix="/api/v1", dependencies=admin_dependencies)
app.include_router(auth_router, prefix="/api/v1")
app.include_router(chat_router, prefix="/api/v1")
app.include_router(reporting_router, prefix="/api/v1")
