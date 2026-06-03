"""Extract text and metadata from PDF files using pdfplumber."""

from pathlib import Path
from typing import TypedDict

import pdfplumber
from loguru import logger


class PageDoc(TypedDict):
    text: str
    metadata: dict


def parse_pdf(pdf_path: Path) -> list[PageDoc]:
    """Parse a single PDF into a list of per-page dicts with text and metadata.

    Bad pages are logged and skipped — never raises on encoding errors.
    """
    source_slug = pdf_path.stem
    docs: list[PageDoc] = []

    try:
        with pdfplumber.open(pdf_path) as pdf:
            title = _extract_title(pdf, source_slug)
            source_url = _infer_source_url(source_slug)

            for page_num, page in enumerate(pdf.pages, start=1):
                try:
                    text = page.extract_text(x_tolerance=2, y_tolerance=2) or ""
                    text = text.strip()
                    if len(text) < 30:
                        # Skip near-empty pages (cover images, blank dividers, etc.)
                        continue
                    docs.append(
                        PageDoc(
                            text=text,
                            metadata={
                                "source": source_slug,
                                "title": title,
                                "page": page_num,
                                "source_url": source_url,
                            },
                        )
                    )
                except Exception as page_exc:  # noqa: BLE001
                    logger.warning(f"Skipping page {page_num} in {pdf_path.name}: {page_exc}")
                    continue

    except Exception as exc:  # noqa: BLE001
        logger.error(f"Failed to open {pdf_path.name}: {exc}")
        return []

    logger.info(f"Parsed {pdf_path.name}: {len(docs)} usable pages")
    return docs


def parse_all_pdfs(raw_dir: Path) -> list[PageDoc]:
    """Parse every PDF in raw_dir and return all page docs."""
    pdfs = sorted(raw_dir.glob("*.pdf"))
    if not pdfs:
        logger.warning(f"No PDF files found in {raw_dir}")
        return []

    all_docs: list[PageDoc] = []
    for pdf_path in pdfs:
        all_docs.extend(parse_pdf(pdf_path))

    logger.info(f"Total pages parsed: {len(all_docs)} from {len(pdfs)} PDFs")
    return all_docs


def _extract_title(pdf: pdfplumber.PDF, fallback: str) -> str:
    """Return the PDF metadata title or fall back to the filename slug."""
    try:
        meta = pdf.metadata or {}
        title = (meta.get("Title") or "").strip()
        return title if title else fallback
    except Exception:  # noqa: BLE001
        return fallback


def _infer_source_url(source_slug: str) -> str:
    """Map a filename slug back to a human-readable source URL for citations."""
    slug_to_url: dict[str, str] = {
        "eu_cpr_305_2011_en": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32011R0305",
        "eu_epbd_2010_31_en": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32010L0031",
        "eu_floods_2007_60_en": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32007L0060",
        "fema_p154_rapid_visual_screening": "https://www.fema.gov/publications/rapid-visual-screening-buildings",
        "fema_p2055_post_disaster_assessment": "https://www.fema.gov/publications/post-disaster-building-safety-evaluation",
        "nist_tn2220_concrete_inspection": "https://nvlpubs.nist.gov/nistpubs/TechnicalNotes/NIST.TN.2220.pdf",
        "nist_gcr_17_917_45_nonlinear_analysis": "https://nvlpubs.nist.gov/nistpubs/gcr/2017/NIST.GCR.17-917-45.pdf",
    }
    return slug_to_url.get(source_slug, f"https://fieldiq.local/sources/{source_slug}")
