"""Download public technical PDF documents for building inspection norms to data/raw/."""

import json
from datetime import datetime, timezone
from pathlib import Path

import requests
from loguru import logger
from tqdm import tqdm

# Direct PDF download URLs for public building/structural engineering documents.
#
# Source selection notes:
# - EUR-Lex uses the older LexUriServ API (?uri=OJ:...) which bypasses the
#   cookie-gated /legal-content/ endpoint that returns HTML to non-browsers.
# - FEMA and NIST documents are served directly from government CDN / S3.
# - JRC bitstream URLs have been replaced with the current publications portal links.
DOCUMENTS: list[dict[str, str]] = [
    # EUR-Lex via LexUriServ — direct OJ PDF, no cookie/JS challenge
    {
        "filename": "eu_cpr_305_2011_en.pdf",
        "source_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=CELEX:32011R0305"
         ,
        "title": "EU Construction Products Regulation No 305/2011",
        "language": "en",
    },
    {
        "filename": "eu_epbd_2010_31_en.pdf",
        "source_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=CELEX:32010L0031"
         ,
        "title": "EU Directive 2010/31/EU — Energy Performance of Buildings",
        "language": "en",
    },
    {
        "filename": "eu_floods_2007_60_en.pdf",
        "source_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=CELEX:32007L0060",
        "title": "EU Directive 2007/60/EC — Assessment and Management of Flood Risks",
        "language": "en",
    },
    # FEMA — US Federal Emergency Management Agency, served from their CDN
    {
        "filename": "fema_p154_rapid_visual_screening.pdf",
        "source_url": (
            "https://www.fema.gov/sites/default/files/2020-07/"
            "fema_rapid-visual-screening-buildings_p-154.pdf"
        ),
        "title": "FEMA P-154: Rapid Visual Screening of Buildings for Potential Seismic Hazards",
        "language": "en",
    },
    {
        "filename": "fema_p2055_post_disaster_assessment.pdf",
        "source_url": (
            "https://www.fema.gov/sites/default/files/documents/fema_"
            "p-2055-post-disaster-building-safety-evaluation-guidance.pdf"
        ),
        "title": "FEMA P-2055: Post-Disaster Building Safety Evaluation",
        "language": "en",
    },
    # NIST — National Institute of Standards and Technology, served from nvlpubs.nist.gov
    {
        "filename": "nist_tn2220_concrete_inspection.pdf",
        "source_url": "https://nvlpubs.nist.gov/nistpubs/TechnicalNotes/NIST.TN.2220.pdf",
        "title": "NIST TN 2220 — Nondestructive Evaluation of Concrete Infrastructure",
        "language": "en",
    },
    {
        "filename": "nist_gcr_17_917_45_nonlinear_analysis.pdf",
        "source_url": "https://nvlpubs.nist.gov/nistpubs/gcr/2017/NIST.GCR.17-917-45.pdf",
        "title": "NIST GCR 17-917-45 — Guidelines for Nonlinear Structural Analysis",
        "language": "en",
    }
]


def _is_pdf(data: bytes) -> bool:
    """Return True if the first 4 bytes match the PDF magic number."""
    return data[:4] == b"%PDF"


def download_documents(raw_dir: Path, force_reload: bool = False) -> list[dict]:
    """Download all configured PDFs into raw_dir and return the manifest entries."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = raw_dir / "manifest.json"

    # Use a realistic browser User-Agent so document servers don't return HTML
    # consent/redirect pages instead of the PDF.
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "application/pdf,*/*;q=0.9",
        "Referer": "https://www.fema.gov/",
    }

    manifest: list[dict] = []

    for doc in tqdm(DOCUMENTS, desc="Downloading documents"):
        dest = raw_dir / doc["filename"]

        if dest.exists() and not force_reload:
            logger.info(f"Skipping {doc['filename']} — already on disk")
            manifest.append(
                {**doc, "date_downloaded": "cached", "status": "ok", "bytes": dest.stat().st_size}
            )
            continue

        logger.info(f"Downloading: {doc['title']}")
        try:
            response = requests.get(
                doc["source_url"],
                headers=headers,
                timeout=60,
                stream=True,
                allow_redirects=True,
            )
            response.raise_for_status()

            # Buffer first chunk to verify we got a PDF and not an HTML error page
            first_chunk = b""
            all_chunks: list[bytes] = []
            for chunk in response.iter_content(chunk_size=8192):
                if not first_chunk:
                    first_chunk = chunk
                all_chunks.append(chunk)

            if not _is_pdf(first_chunk):
                logger.warning(
                    f"Skipping {doc['filename']}: response is not a PDF "
                    f"(Content-Type: {response.headers.get('Content-Type', 'unknown')})"
                )
                manifest.append(
                    {**doc, "date_downloaded": None, "status": "not_pdf", "error": "Response not a PDF"}
                )
                continue

            dest.write_bytes(b"".join(all_chunks))
            size = dest.stat().st_size
            manifest.append(
                {
                    **doc,
                    "date_downloaded": datetime.now(timezone.utc).isoformat(),
                    "status": "ok",
                    "bytes": size,
                }
            )
            logger.info(f"✓ {doc['filename']} ({size:,} bytes)")

        except requests.RequestException as exc:
            logger.warning(f"✗ {doc['filename']}: {exc}")
            manifest.append({**doc, "date_downloaded": None, "status": "failed", "error": str(exc)})

    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    ok_count = sum(1 for m in manifest if m["status"] == "ok")
    logger.info(f"Pipeline — downloaded {ok_count}/{len(DOCUMENTS)} documents")

    if ok_count == 0:
        logger.error("No documents were downloaded — check network access and source URLs")

    return manifest
