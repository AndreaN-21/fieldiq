"""CLI entry point for the FieldIQ ingestion pipeline — run once before starting the app."""

import argparse
import sys
from pathlib import Path

from loguru import logger


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.chunk import chunk_documents
from pipeline.download import download_documents
from pipeline.embed import embed_and_store
from pipeline.parse import parse_all_pdfs


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="FieldIQ data ingestion pipeline: download → parse → chunk → embed"
    )
    parser.add_argument(
        "--force-reload",
        action="store_true",
        help="Re-download all PDFs and rebuild the ChromaDB index from scratch",
    )
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=Path("./data/raw"),
        help="Directory where PDFs are stored (default: ./data/raw)",
    )
    parser.add_argument(
        "--chroma-dir",
        type=Path,
        default=Path("./data/chroma"),
        help="ChromaDB persistence directory (default: ./data/chroma)",
    )
    return parser


def run(raw_dir: Path, chroma_dir: Path, force_reload: bool) -> None:
    """Execute the full ingestion pipeline."""
    logger.info("=== FieldIQ Pipeline Start ===")

    # Step 1 — Download
    logger.info("Step 1/4 — Downloading PDFs …")
    download_documents(raw_dir, force_reload=force_reload)

    # Check what PDFs are actually available (downloaded + any manually placed)
    available_pdfs = list(raw_dir.glob("*.pdf"))
    if not available_pdfs:
        logger.error(
            f"No PDF files found in {raw_dir} after download step. "
            "Check network access or manually place PDFs in that directory."
        )
        sys.exit(1)
    logger.info(f"{len(available_pdfs)} PDF(s) available for processing")

    # Step 2 — Parse
    logger.info("Step 2/4 — Parsing PDFs …")
    page_docs = parse_all_pdfs(raw_dir)
    if not page_docs:
        logger.error("No pages extracted — check PDF files in {raw_dir}")
        sys.exit(1)

    # Step 3 — Chunk
    logger.info("Step 3/4 — Chunking …")
    chunks = chunk_documents(page_docs)

    # Step 4 — Embed and store
    logger.info("Step 4/4 — Embedding and storing in ChromaDB …")
    collection = embed_and_store(chunks, chroma_dir, force_reload=force_reload)

    logger.info(f"=== Pipeline complete — {collection.count()} chunks indexed ===")


if __name__ == "__main__":
    parser = _build_parser()
    args = parser.parse_args()
    run(raw_dir=args.raw_dir, chroma_dir=args.chroma_dir, force_reload=args.force_reload)
