"""Retrieve relevant norm chunks from ChromaDB for a given query."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from loguru import logger

from config import settings
from pipeline.embed import COLLECTION_NAME, EMBED_MODEL

MAX_DISTANCE = 0.92


@dataclass
class RetrievedChunk:
    text: str
    source: str
    title: str
    page: int
    source_url: str
    chunk_id: str
    distance: float


def _get_collection() -> chromadb.Collection:
    """Open the ChromaDB collection (shared across requests via module-level cache)."""
    ef = SentenceTransformerEmbeddingFunction(model_name=EMBED_MODEL)
    client = chromadb.PersistentClient(path=str(Path(settings.chroma_persist_dir).resolve()))
    return client.get_collection(name=COLLECTION_NAME, embedding_function=ef)


# Module-level cache so the collection is opened once per process lifetime
_collection_cache: chromadb.Collection | None = None


def _collection() -> chromadb.Collection:
    global _collection_cache
    if _collection_cache is None:
        _collection_cache = _get_collection()
    return _collection_cache


def retrieve(query: str, n_results: int = 5) -> list[RetrievedChunk]:
    """Query ChromaDB and return the top-k relevant chunks, filtered by distance.

    Returns an empty list if the collection is unavailable or has no matches within
    the relevance threshold — callers must handle this gracefully.
    """
    try:
        col = _collection()
    except Exception as exc:  # noqa: BLE001
        logger.error(f"ChromaDB collection unavailable: {exc}")
        return []

    results = col.query(
        query_texts=[query],
        n_results=min(n_results, col.count()),
        include=["documents", "metadatas", "distances"],
    )

    chunks: list[RetrievedChunk] = []
    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    for text, meta, dist in zip(documents, metadatas, distances):
        if dist > MAX_DISTANCE:
            logger.debug(f"Filtered chunk (distance {dist:.3f} > {MAX_DISTANCE}): {meta.get('chunk_id')}")
            continue
        chunks.append(
            RetrievedChunk(
                text=text,
                source=meta.get("source", "unknown"),
                title=meta.get("title", "Unknown document"),
                page=int(meta.get("page", 0)),
                source_url=meta.get("source_url", ""),
                chunk_id=meta.get("chunk_id", ""),
                distance=dist,
            )
        )

    logger.debug(f"retrieve('{query[:60]}…') → {len(chunks)} chunks kept")
    return chunks


def indexed_document_count() -> int:
    """Return total number of indexed chunks (used by the health endpoint)."""
    try:
        return _collection().count()
    except Exception:  # noqa: BLE001
        return 0
