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
        "filename": "eu_iot_1275_2024_en.pdf",
        "source_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=OJ:L_202401275",
        "title": "Directive (EU) 2024/1275 of the European Parliament and of the council",
        "language": "en",
    },
   {
        "filename": "seco_buildwise_guide_entretien_2023.pdf",
        "source_url": "https://ecobuild.brussels/wp-content/uploads/2023/02/31400-fr-unprotected-guide-de-l-entretien-pour-des-batiments-durables-2023.pdf",
        "title": "Guide de l'entretien pour des bâtiments durables – Édition 2023 (Buildwise / SECO)",
        "language": "fr",
    },
    {
        "filename": "cstc_nit271_maconneries_2020.pdf",
        "source_url": "https://www.benor.be/wp-content/uploads/2020/03/NIT_271.pdf",
        "title": "CSTC NIT 271 – Exécution des maçonneries (Belgique, 2020)",
        "language": "fr",
    },
    {
        "filename": "cneaf_pathologie_maisons_2018.pdf",
        "source_url": "http://cneaf.fr/wp-content/uploads/2018/09/CR-162eTRNTJ-du-15-juin-2018-1.pdf",
        "title": "CNEAF – Pathologie des maisons individuelles: les désordres récurrents (2018)",
        "language": "fr",
    },
    # NIST — National Institute of Standards and Technology, served from nvlpubs.nist.gov
    {
        "filename": "nist_tn2220_concrete_inspection.pdf",
        "source_url": "https://nvlpubs.nist.gov/nistpubs/TechnicalNotes/NIST.TN.2220.pdf",
        "title": "NIST TN 2220 — Nondestructive Evaluation of Concrete Infrastructure",
        "language": "en",
    },
    {
        "filename": "jrc_handbook2_reliability.pdf",
        "source_url": "https://eurocodes.jrc.ec.europa.eu/sites/default/files/2021-12/handbook2.pdf",
        "title": "JRC Handbook 2 — Reliability Backgrounds for Eurocodes",
        "language": "en",
    },
    {
        "filename": "cstc_contact_2018_3_fissuration.pdf",
        "source_url": "https://www.buildwise.be/media/1o2nnrdt/contact_fr_03_2018.pdf",
        "title": "CSTC Contact 2018/3 – Fissuration dans les bâtiments et durabilité du béton",
        "language": "fr",
    },
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
