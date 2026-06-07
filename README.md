# FieldIQ — Building Defect Intelligence Assistant

A RAG-powered assistant that turns a field inspector's text description into a
structured defect analysis — classification, severity score, and verbatim excerpts
from real technical standards — in under five seconds.

---

## What problem does it solve, and for whom?

**User:** A SECO field inspector conducting an on-site building inspection.

When an inspector observes a defect — efflorescence on a basement wall, a diagonal
crack from a window lintel, spalling on a reinforced concrete column — they face four
sequential tasks under time pressure, usually on a phone:

1. Classify the defect type and affected component
2. Identify the applicable technical standard
3. Assign a severity and justify it
4. Produce a documentation entry for the report

Today this means consulting dense PDF norms from memory, switching between tools,
and writing free-form notes that vary in quality between inspectors.

FieldIQ collapses all four steps into a single text input. The inspector describes
what they see; the system returns a structured analysis grounded in real documents —
not generated from model weights alone.

The core problem being solved is **knowledge retrieval under field conditions**. A
junior inspector six months into the job should be able to produce a normatively
grounded report as quickly as a senior with ten years of experience. Today they
cannot.

---

## Why is this relevant to SECO?

SECO's core asset is accumulated inspection knowledge: thousands of defect
observations, severity assessments, and norm references, generated over decades of
activity. That knowledge currently sits in PDFs and internal systems.

FieldIQ is a direct prototype of how SECO could productize that corpus. This MVP
uses public technical documents as the knowledge base. Replace them with SECO's
proprietary inspection reports and the value compounds: the system learns which
defect patterns appear most frequently, which norms are cited most often, and how
severity assessments vary across building types and age cohorts.

One data point worth noting: one of the documents in this MVP's knowledge base —
the *Guide de l'entretien pour des bâtiments durables* (Buildwise, 2023) — was
co-authored by SECO itself. The architecture here is a direct analogue of what
SECO would build on top of its own corpus.

The project also addresses a structural risk for any inspection firm: knowledge
concentration. When senior inspectors leave or retire, their pattern-recognition
leaves with them. A RAG system trained on their past assessments partially
preserves it.

---

## Data sources

All sources are publicly accessible without login. No paywalled standards (AFNOR,
NF) were used. The corpus is intentionally small — quality of parsing and retrieval
matters more than breadth for an MVP.

| File | Source | What it contributes |
|---|---|---|
| `seco_buildwise_guide_entretien_2023.pdf` | [Buildwise / SECO, 2023](https://ecobuild.brussels/wp-content/uploads/2023/02/31400-fr-unprotected-guide-de-l-entretien-pour-des-batiments-durables-2023.pdf) | Building maintenance guide covering moisture, facades, roofing, structures. **Co-authored by SECO.** |
| `cstc_nit271_maconneries_2020.pdf` | [BENOR / CSTC NIT 271, 2020](https://www.benor.be/wp-content/uploads/2020/03/NIT_271.pdf) | Belgian masonry execution standard — wall bonding, waterproofing, efflorescence |
| `cneaf_pathologie_maisons_2018.pdf` | [CNEAF, 2018](http://cneaf.fr/wp-content/uploads/2018/09/CR-162eTRNTJ-du-15-juin-2018-1.pdf) | French expert report on recurring residential building pathologies — cracks, infiltrations, foundations |
| `cstc_contact_2018_3_fissuration.pdf` | [CSTC Contact 2018/3](https://www.buildwise.be/media/1o2nnrdt/contact_fr_03_2018.pdf) | Technical note on cracking caused by soil movement and concrete durability |
| `nist_tn2220_concrete_inspection.pdf` | [NIST TN 2220](https://nvlpubs.nist.gov/nistpubs/TechnicalNotes/NIST.TN.2220.pdf) | Nondestructive evaluation of concrete infrastructure — spalling, rebar exposure, crack mapping |
| `jrc_handbook2_reliability.pdf` | [JRC Handbook 2](https://eurocodes.jrc.ec.europa.eu/sites/default/files/2021-12/handbook2.pdf) | Eurocode EN 1990 reliability backgrounds — structural limit states and safety concepts |
| `eu_cpr_305_2011_en.pdf` | [EU CPR 305/2011](https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=CELEX:32011R0305) | EU Construction Products Regulation — regulatory framework for construction product compliance |
| `eu_epbd_2024_1275_en.pdf` | [EU EPBD 2024/1275](https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=OJ:L_202401275) | Recast Energy Performance of Buildings Directive — envelope and energy requirements |


---

## Technical decisions and trade-offs

**Multilingual embedding model (`paraphrase-multilingual-MiniLM-L12-v2`)**
The corpus mixes French (CSTC/Buildwise guides) and English (NIST, JRC). An
English-only model (`all-MiniLM-L6-v2`) was used first and produced poor retrieval
on French documents — cosine distances were above the relevance threshold even for
clearly applicable chunks. Switching to the multilingual model resolved this.
Trade-off: ~500 MB vs ~90 MB model size, slightly slower initial embedding.

**ChromaDB as vector store**
Zero infrastructure, fully reproducible, runs as a local file store. Chosen
specifically to satisfy the challenge's "public and reproducible" constraint.
Trade-off: not suitable for production multi-tenant workloads. Would be replaced
with Weaviate or Qdrant on managed infrastructure.

**`MAX_DISTANCE = 0.92` in retrieval**
Initially set to 0.80, but French-language chunks were being filtered out at
distances of 0.74–0.80 when queried in English, even when semantically relevant.
Raised to 0.92. The LLM prompt serves as a second filter — the model is
instructed to only cite chunks that are actually relevant, and to return an empty
array otherwise.

**LLM-based analysis (GPT-4o-mini)**
Fast (2–4s), cost-effective, and reliably follows strict JSON schema instructions.
The prompt explicitly prohibits norm hallucination: the model may only cite
documents present in the retrieved context. Tested on 10+ defect descriptions.
Trade-off: for highly ambiguous descriptions a larger model produces more nuanced
severity assessments.

**pdfplumber over PyMuPDF**
More reliable on column-based and technically dense PDFs. Per-page error handling
means one bad page does not abort the pipeline. Trade-off: slower on large
documents.

**SQLite for query logging**
Sufficient for prototype observability. Trade-off: replace with PostgreSQL in
production.

## What goes to production tomorrow vs. what gets thrown away

**Keep — production-ready today:**
- RAG pipeline architecture (retrieve → augment → generate). The pattern is sound regardless of the document corpus.
- Prompt design. The CRITICAL RULES block (no norm hallucination, mandatory citations, `p.<n>` fallback for unnumbered guides) was developed against real defect descriptions and solves real failure modes.
- FastAPI structure — async handlers, typed request/response models, 503 vs 500 distinction at the API boundary.
- Pydantic v2 models — strict validation catches malformed LLM output before it reaches the frontend.
- `_sanitize()` post-processor — defensive layer against the specific GPT-4o-mini formatting regressions observed in testing.

**Throw away:**
- Manual PDF seeding → replace with a scheduled ingestion job that pulls from SECO's report management system.
- Local ChromaDB → replace with Weaviate or Qdrant on managed infrastructure with access control.
- `paraphrase-multilingual-MiniLM-L12-v2` → replace with a model fine-tuned on SECO's defect vocabulary after collecting inspector feedback.
- SQLite query log → replace with PostgreSQL + a metrics dashboard (Grafana or Metabase).
- `MAX_DISTANCE` hardcoded at 0.92 → replace with a per-query confidence score and a calibrated rejection threshold.

---

## If I had 2 more months

**Photo upload with VLM detection.** Inspector attaches a photo; a vision-language
model auto-populates the description field and adds a visual defect classification.
The text flow stays identical downstream.

**Inspector feedback loop.** Thumbs-up / correction on every result. Corrections
become labelled training data. After 500–1000 corrections, fine-tune the embedding
model on SECO's specific defect vocabulary.

**SECO corpus integration.** Replace public PDFs with SECO's actual past inspection
reports as the knowledge base. The retrieval quality improves as the corpus grows.
The system's answers become SECO's institutional knowledge, not generic norms.

**Mobile PWA.** Optimised for one-handed phone use with offline support. The
current React UI works on mobile but was not designed for it.

**Test suite.** First three test targets: (1) RAG retrieval regression — known
defect queries must return chunks above a minimum relevance threshold; (2) LLM
response parser — fuzz tests against malformed and truncated JSON; (3) API error
paths — 422 on short descriptions, 503 on API failure, never a raw 500.

---

## Setup

### Prerequisites

- Python 3.9+
- Node.js 18+
- An OpenAI API key (or compatible endpoint)

---

### Docker (recommended)

Runs the full stack (backend + frontend).

**Prerequisites:** Docker and Docker Compose v2.

**1. Environment variables**

```bash
cp .env.example .env
```

Edit `.env` and set at minimum:

```
OPENAI_API_KEY=your_key_here
```

**2. Build and start**

```bash
docker compose up --build
```

| Service | URL |
|---|---|
| App | http://localhost |
| API docs | http://localhost:8000/docs |
| Health | http://localhost:8000/api/health |

**First run** takes 3–5 minutes: the backend downloads ~8 PDFs, embeds all chunks, and caches the HuggingFace model. Subsequent starts are instant (data is persisted in Docker volumes).

**Stop**

```bash
docker compose down          # keeps data
docker compose down -v       # also deletes all volumes (full reset)
```

**Optional — change the backend host port** (default `8000`):

```
# .env
BACKEND_PORT=9000
```

---

### Manual setup

### 1. Environment variables

```bash
cp .env.example .env
```

Edit `.env` and set at minimum:

```
OPENAI_API_KEY=your_key_here
OPENAI_BASE_URL=https://api.openai.com/v1   # or your custom endpoint
```

### 2. Backend — install dependencies

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Build the knowledge base

Downloads the PDF documents, parses them, and builds the ChromaDB index.
Run once (or with `--force-reload` to rebuild from scratch).

```bash
cd backend
python pipeline/run_pipeline.py
```

This takes ~2 minutes on first run (downloads ~8 PDFs and embeds all chunks).

### 4. Start the backend

```bash
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

API: `http://localhost:8000`  
Docs: `http://localhost:8000/docs`  
Health: `http://localhost:8000/api/health` → `{"status": "ok", "indexed_documents": N}`

### 5. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

App: `http://localhost:5173`

### Environment variables

| Variable | Default | Description |
|---|---|---|
| `OPENAI_API_KEY` | — | **Required** |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | Override for compatible endpoints |
| `OPENAI_MODEL` | `gpt-4o-mini` | Any OpenAI-compatible model |
| `CHROMA_PERSIST_DIR` | `./data/chroma` | ChromaDB path (relative to `backend/`) |
| `SQLITE_DB_PATH` | `./data/app.db` | Query log |