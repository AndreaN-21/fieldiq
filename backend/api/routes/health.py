"""GET /api/health — liveness and index status check."""

from fastapi import APIRouter
from loguru import logger

from core.rag import indexed_document_count

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    """Return service status and the number of indexed chunks."""
    count = indexed_document_count()
    logger.debug(f"Health check — indexed_documents={count}")
    return {"status": "ok", "indexed_documents": count}
