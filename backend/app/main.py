from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.health import router as health_router
from app.api.v1.data_source_types import router as data_source_router
from app.api.v1.data_sources import router as data_sources_router
from app.api.v1.categories import router as categories_router
from app.api.v1.faq_classifications import router as faq_classifications_router

app = FastAPI(title="Scholarship Chatbot Admin Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/api/v1")
app.include_router(data_source_router, prefix="/api/v1")
app.include_router(data_sources_router, prefix="/api/v1")
app.include_router(categories_router, prefix="/api/v1")
app.include_router(faq_classifications_router, prefix="/api/v1")
