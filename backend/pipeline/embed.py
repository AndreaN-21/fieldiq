"""Embed text chunks with all-MiniLM-L6-v2 and persist them in ChromaDB."""

from pathlib import Path

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from loguru import logger

from pipeline.chunk import Chunk

COLLECTION_NAME = "building_norms"
EMBED_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
# Batch size keeps memory usage bounded when embedding thousands of chunks
BATCH_SIZE = 256


def get_embedding_function() -> SentenceTransformerEmbeddingFunction:
    """Return the shared embedding function (downloads model on first call)."""
    return SentenceTransformerEmbeddingFunction(model_name=EMBED_MODEL)


def embed_and_store(chunks: list[Chunk], chroma_dir: Path, force_reload: bool = False) -> chromadb.Collection:
    """Embed chunks and upsert them into the ChromaDB persistent collection.

    Uses cosine distance so that the 0.8 relevance filter in rag.py is consistent
    with how sentence-transformers are normally evaluated.
    """
    chroma_dir.mkdir(parents=True, exist_ok=True)

    ef = get_embedding_function()
    client = chromadb.PersistentClient(path=str(chroma_dir))

    if force_reload:
        try:
            client.delete_collection(COLLECTION_NAME)
            logger.info(f"Deleted existing collection '{COLLECTION_NAME}'")
        except Exception:  # noqa: BLE001
            pass

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"},
    )

    # Upsert in batches to avoid OOM on large corpora
    total = len(chunks)
    for batch_start in range(0, total, BATCH_SIZE):
        batch = chunks[batch_start : batch_start + BATCH_SIZE]

        ids = [c["chunk_id"] for c in batch]
        texts = [c["text"] for c in batch]
        metadatas = [c["metadata"] for c in batch]

        collection.upsert(ids=ids, documents=texts, metadatas=metadatas)
        logger.debug(f"Upserted batch {batch_start}–{batch_start + len(batch)} / {total}")

    logger.info(f"Collection '{COLLECTION_NAME}' now has {collection.count()} chunks")
    return collection
