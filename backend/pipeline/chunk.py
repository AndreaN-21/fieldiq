"""Split page-level documents into overlapping text chunks for embedding."""

from langchain_text_splitters import RecursiveCharacterTextSplitter
from loguru import logger

from pipeline.parse import PageDoc


class Chunk(PageDoc):
    chunk_index: int # Index of the chunk within its source page (0-based)
    chunk_id: str # Unique ID for the chunk, e.g. "{source}_p{page}_c{chunk_index}"


def chunk_documents(docs: list[PageDoc], chunk_size: int = 400, chunk_overlap: int = 50) -> list[Chunk]:
    """Split each page doc into overlapping chunks, preserving all metadata.

    Uses character-level splitting with ~400 token target size (1 token ≈ 4 chars,
    so 400 tokens ≈ 1600 chars — the splitter uses chars, not tokens).
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size * 4,  # approx chars per token
        chunk_overlap=chunk_overlap * 4,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    chunks: list[Chunk] = []

    for doc in docs:
        splits = splitter.split_text(doc["text"])
        source = doc["metadata"]["source"]
        page = doc["metadata"]["page"]

        for idx, split_text in enumerate(splits):
            chunk_id = f"{source}_p{page}_c{idx}"
            chunks.append(
                Chunk(
                    text=split_text,
                    metadata={**doc["metadata"], "chunk_index": idx, "chunk_id": chunk_id},
                    chunk_index=idx,
                    chunk_id=chunk_id,
                )
            )

    logger.info(f"Chunked {len(docs)} pages into {len(chunks)} chunks")
    return chunks
