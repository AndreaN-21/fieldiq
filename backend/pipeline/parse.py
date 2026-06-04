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
        "eu_iot_1275_2024_en": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=OJ:L_202401275",
        "seco_buildwise_guide_entretien_2023": "https://ecobuild.brussels/wp-content/uploads/2023/02/31400-fr-unprotected-guide-de-l-entretien-pour-des-batiments-durables-2023.pdf",
        "cstc_nit271_maconneries_2020": "https://www.benor.be/wp-content/uploads/2020/03/NIT_271.pdf",
        "cneaf_pathologie_maisons_2018": "http://cneaf.fr/wp-content/uploads/2018/09/CR-162eTRNTJ-du-15-juin-2018-1.pdf",
        "nist_tn2220_concrete_inspection": "https://nvlpubs.nist.gov/nistpubs/TechnicalNotes/NIST.TN.2220.pdf",
        "jrc_handbook2_reliability": "https://eurocodes.jrc.ec.europa.eu/sites/default/files/2021-12/handbook2.pdf",
        "cstc_contact_2018_3_fissuration": "https://www.buildwise.be/media/1o2nnrdt/contact_fr_03_2018.pdf",
    }
    return slug_to_url.get(source_slug, f"https://fieldiq.local/sources/{source_slug}")