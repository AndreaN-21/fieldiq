"""POST /api/analyze — orchestrate RAG retrieval + LLM analysis + SQLite logging."""

from __future__ import annotations

import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

import openai
from fastapi import APIRouter, HTTPException
from loguru import logger

from api.models import AnalysisResult, AnalyzeRequest, NormReference
from config import settings
from core.analyzer import analyze
from core.rag import retrieve

router = APIRouter()


def _init_db(db_path: Path) -> None:
    """Create the query_log table if it does not exist."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db_path))
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS query_log (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp       TEXT    NOT NULL,
            description     TEXT    NOT NULL,
            defect_type     TEXT,
            severity        TEXT,
            chunks_used     INTEGER,
            model_used      TEXT,
            response_ms     REAL
        )
        """
    )
    con.commit()
    con.close()


def _log_query(
    description: str,
    result: AnalysisResult | None,
    chunks_used: int,
    response_ms: float,
) -> None:
    """Append one row to the SQLite query log — failures are silently ignored."""
    try:
        db_path = Path(settings.sqlite_db_path).resolve()
        _init_db(db_path)
        con = sqlite3.connect(str(db_path))
        con.execute(
            """
            INSERT INTO query_log (timestamp, description, defect_type, severity,
                                   chunks_used, model_used, response_ms)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now(timezone.utc).isoformat(),
                description[:500],
                result.defect_type if result else None,
                result.severity if result else None,
                chunks_used,
                settings.openai_model,
                round(response_ms, 2),
            ),
        )
        con.commit()
        con.close()
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Query logging failed (non-fatal): {exc}")


@router.post("/analyze", response_model=AnalysisResult)
async def analyze_defect(request: AnalyzeRequest) -> AnalysisResult:
    """Analyze a defect description: retrieve relevant norms, classify, return structured result."""
    t0 = time.monotonic()

    # Step 1 — RAG retrieval
    chunks = retrieve(request.description, n_results=5)
    logger.info(f"/api/analyze — {len(chunks)} chunks retrieved for query")

    # Step 2 — LLM analysis
    try:
        raw = analyze(request.description, chunks)
    except openai.OpenAIError as exc:
        logger.error(f"OpenAI API error: {exc}")
        raise HTTPException(
            status_code=503,
            detail="AI analysis service temporarily unavailable. Please retry in a moment.",
        ) from exc
    except ValueError as exc:
        logger.error(f"LLM response parse error: {exc}")
        raise HTTPException(
            status_code=503,
            detail="AI analysis returned an unexpected format. Please retry.",
        ) from exc

    # Step 3 — Validate and coerce into the response model
    try:
        result = AnalysisResult(
            defect_type=raw.get("defect_type", "Unknown"),
            affected_component=raw.get("affected_component", "Unknown"),
            likely_cause=raw.get("likely_cause", ""),
            severity=raw.get("severity", "Low"),
            severity_justification=raw.get("severity_justification", ""),
            norm_references=[
                NormReference(**ref) for ref in raw.get("norm_references", [])[:3]
            ],
            report_template=raw.get("report_template", ""),
            disclaimer=raw.get(
                "disclaimer",
                "AI-assisted analysis based on public technical standards. "
                "Must be reviewed by a certified inspector before inclusion in official reports.",
            ),
        )
    except Exception as exc:  # noqa: BLE001
        logger.error(f"AnalysisResult construction failed: {exc} | raw={raw}")
        raise HTTPException(
            status_code=503,
            detail="AI analysis returned an incomplete response. Please retry.",
        ) from exc

    elapsed_ms = (time.monotonic() - t0) * 1000
    _log_query(request.description, result, len(chunks), elapsed_ms)
    logger.info(f"/api/analyze — completed in {elapsed_ms:.0f} ms (severity={result.severity})")

    return result
