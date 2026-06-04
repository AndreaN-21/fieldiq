"""Split page-level documents into overlapping text chunks for embedding."""

from langchain_text_splitters import RecursiveCharacterTextSplitter
from loguru import logger
import re

from pipeline.parse import PageDoc


class Chunk(PageDoc):
    chunk_index: int # Index of the chunk within its source page (0-based)
    chunk_id: str # Unique ID for the chunk, e.g. "{source}_p{page}_c{chunk_index}"

# Patterns that identify section/article numbers in French and English technical documents.
# Checked against the first 5 lines of each chunk — order matters (most specific first).
_SECTION_PATTERNS: list[re.Pattern] = [
    # "6.2.3 TITRE" or "6.2.3. Titre" — numbered sections
    re.compile(r"^\s*(\d+(?:\.\d+)+\.?)\s+\S"),
    # "Article 5.2" / "article 5"
    re.compile(r"^\s*[Aa]rticle\s+(\d+(?:\.\d+)*)"),
    # "§ 5.3.2"
    re.compile(r"^\s*§\s*(\d+(?:\.\d+)*)"),
    # "Section 3.2" / "section 3"
    re.compile(r"^\s*[Ss]ection\s+(\d+(?:\.\d+)*)"),
    # "Chapitre 5" / "Chapter 5"
    re.compile(r"^\s*(?:Chapitre|Chapter)\s+(\d+)", re.IGNORECASE),
    # Tableau / Figure / Annexe references ("Tableau 6", "Annexe A")
    re.compile(r"^\s*(?:Tableau|Figure|Annexe|Table|Annex)\s+([A-Z0-9]+)", re.IGNORECASE),
    # Top-level numbered item: "3 MATÉRIAUX" (single number + uppercase word)
    re.compile(r"^\s*(\d+)\s+[A-ZÀÂÄÉÈÊËÎÏÔÙÛÜ]{3,}"),
]

def _extract_section_header(text: str) -> str:
    """Return the most specific section/article number found in the first lines of text.
 
    Checks the first 5 non-empty lines against common section-numbering patterns
    used in Belgian/French construction norms (NIT, DTU, EN).
 
    Returns an empty string if no recognisable section number is found — callers
    should fall back to the page number.
    """
    lines = [line for line in text.splitlines() if line.strip()][:5]
    for line in lines:
        for pattern in _SECTION_PATTERNS:
            match = pattern.match(line)
            if match:
                return match.group(1)
    return ""
 

def _build_section_map(docs: list[PageDoc]) -> dict[int, str]:
    """Scorre tutti i documenti e propaga l'ultimo numero di sezione trovato.

    Se la pagina 104 non ha un header, eredita la sezione dell'ultima pagina
    che ce l'aveva (es. pagina 98 con '6.3 Couvre-murs').
    """
    section_map: dict[int, str] = {}
    last_section = ""

    for doc in docs:
        section = _extract_section_header(doc["text"])
        if section:
            last_section = section
        section_map[doc["metadata"]["page"]] = last_section

    return section_map

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

    from itertools import groupby 

    for source_slug, source_docs in groupby(docs, key=lambda d: d["metadata"]["source"]):
        source_docs = list(source_docs)
        section_map = _build_section_map(source_docs)  

        for doc in source_docs:
            splits = splitter.split_text(doc["text"])
            page = doc["metadata"]["page"]
            page_section = section_map.get(page, "")

            for idx, split_text in enumerate(splits):
                chunk_id = f"{source_slug}_p{page}_c{idx}"
                chunks.append(Chunk(
                    text=split_text,
                    metadata={
                        **doc["metadata"],
                        "chunk_index": idx,
                        "chunk_id": chunk_id,
                        "section": page_section,
                    },
                    chunk_index=idx,
                    chunk_id=chunk_id,
                ))

    logger.info(f"Chunked {len(docs)} pages into {len(chunks)} chunks")
    return chunks