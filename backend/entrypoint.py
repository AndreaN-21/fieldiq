"""Container entrypoint: auto-run the ingestion pipeline if ChromaDB is empty."""
import os
import subprocess
import sys
from pathlib import Path

import chromadb

CHROMA_DIR = Path(os.environ.get("CHROMA_PERSIST_DIR", "./data/chroma"))
COLLECTION_NAME = "building_norms"


def _collection_ready() -> bool:
    if not CHROMA_DIR.exists():
        return False
    try:
        client = chromadb.PersistentClient(path=str(CHROMA_DIR.resolve()))
        col = client.get_collection(name=COLLECTION_NAME)
        return col.count() > 0
    except Exception:
        return False


if not _collection_ready():
    print(
        f"ChromaDB collection '{COLLECTION_NAME}' is missing or empty — "
        "running ingestion pipeline (this takes a few minutes on first boot)...",
        flush=True,
    )
    result = subprocess.run([sys.executable, "pipeline/run_pipeline.py"])
    if result.returncode != 0:
        print("Pipeline failed — aborting startup.", flush=True)
        sys.exit(1)
 
os.execvp("uvicorn", ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"])
