"""FieldIQ FastAPI application entrypoint."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from config import settings
from api.routes.analyze import router as analyze_router
from api.routes.health import router as health_router

app = FastAPI(
    title="FieldIQ API",
    description="Building defect intelligence assistant for field inspectors",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://localhost:5173", "http://localhost:8090"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

app.include_router(analyze_router, prefix="/api")
app.include_router(health_router, prefix="/api")


@app.on_event("startup")
async def _startup() -> None:
    logger.info(f"FieldIQ API starting — model={settings.openai_model}")
