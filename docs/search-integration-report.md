# Search and Integration: Work Report

**Owner:** Tanjim Sohan · **Branch:** `feature/search-integration` · **Course:** COMP 3710

This report explains everything done for the "Search and integration" module so you can understand, demo and defend it. Written for: Tanjim, who has to explain the work to Dr. Teimoori.

---

## 1. What this module was supposed to do

From the proposal (sections 7 and 9) your module owns: GitHub setup, the search API, Docker Compose, end-to-end tests and documentation, plus combining the other three modules into one working system.

## 2. What I found when I started

| Module | Branch | State |
|---|---|---|
| Ingestion (Tahmid) | `feature/ingestion-storage` | Complete. Upload API, hashing, storage, tests. |
| Extraction (Diya) | `feature/content-extraction` | Complete. Readers, chunker, OCR check, DB saving. |
| AI indexing (Jahid) | `feature/ai-indexing-similarity` | Embeddings, Qdrant storage, exact-duplicate records. **No summaries, no near-duplicate or related records.** |
| Search and integration | `feature/search-integration` | Empty (README only). |

Nothing connected the modules: no code called extraction after an upload, and no code called indexing after extraction.

## 3. What I did, step by step

### 3.1 Merged the three branches
Merged ingestion, extraction and AI indexing into `feature/search-integration`. Two files conflicted (`app/shared/models/__init__.py` and `requirements.txt`) because each teammate added their own lines; I kept both sides. After the merge, the teammates' own **104 tests all passed**.

### 3.2 Built the pipeline (`app/pipeline/service.py`)
`process_document()` runs one file through every stage, using each teammate's existing functions:

1. **Extract** (Diya's `extract_and_save`) saves text and ordered chunks.
2. **Summarize** (mine) saves a summary on `DocumentContent.summary`.
3. **Index** (Jahid's `index_document`) stores chunk vectors in Qdrant and records exact duplicates.
4. **Compare** (mine) records near-duplicate and related matches.

If a file has no text (scanned PDF or image) it gets the new status `ocr_needed` and is not embedded, as the proposal requires. Any other error sets `failed` and the error message is returned instead of crashing.

### 3.3 Automatic processing on upload
`POST /files` now schedules the pipeline as a FastAPI background task, so the upload returns immediately and the client polls `GET /files/{id}` until the status is `indexed`. This needed three tiny edits to Tahmid's `routes.py`. The background job opens its own database session because the request's session is closed by then. `POST /files/{id}/process` re-runs it manually.

### 3.4 Summaries (`app/summarization/`)
You said to use whatever is best from my side until Jahid adds his. I chose a **local extractive summarizer**: it embeds every sentence with the project's existing model and keeps the 3 sentences closest to the document's average meaning, in original order. It needs no API key or cost and works offline in Docker. It is isolated behind one function (`summarize_text`), so when Jahid adds his summarizer you change only `app/summarization/__init__.py`.
*Trade-off:* it picks existing sentences, so it is less fluent than an LLM summary.

### 3.5 Similarity labels (`app/pipeline/similarity.py`)
Jahid's `search_similar_files` labels a file using its single best chunk. That is risky: two unrelated documents sharing one boilerplate paragraph would be called near-duplicates. I score a candidate at **document level**: for each chunk of the new file, take its best match in the candidate, then average over all chunks (0 where nothing matches). Only files that are alike overall score high.

Labels: exact duplicate (same SHA-256, Jahid's code) → near duplicate (score ≥ 0.95) → related (score ≥ 0.45) → otherwise nothing is stored.

### 3.6 Threshold tuning (the proposal said 0.95 would be tuned)
I measured real scores with the project's model (`all-MiniLM-L6-v2`):

| Pair | Cosine score |
|---|---|
| Document vs lightly edited copy | 0.997 |
| Two related AI documents | 0.47 to 0.56 |
| Unrelated (AI vs cooking) | about 0.02 |

Jahid's default "related" threshold of 0.75 never fires for related documents with this model. I first tried 0.40, but the notes file ("reading list") was flagged related to the AI paper at 0.42 to 0.43, which looked like a false positive, so I set **0.45**. Near-duplicate stays 0.95. Both are environment variables. *Caveat:* tuned on only 8 sample files; more varied samples could move it.

### 3.7 Search (`GET /search`, `app/search/`)
1. Embed the query with the **same model** as the documents.
2. Ask Qdrant for the closest chunks (5 times `limit`, so grouping still fills the page).
3. Group by file and keep each file's best chunk, giving **one result per document**.
4. Look up filename, storage path and summary in PostgreSQL; skip files not `indexed`.
5. Return `file_id, filename, extension, summary, score, matched_excerpt, storage_path`.

Parameters: `q`, `limit`, `min_score` (default 0.2), `extension` filter.

### 3.8 Other endpoints
`GET /files` (list), `GET /files/{id}/similar`, `POST /files/{id}/process`, `GET /health`.

### 3.9 Docker
`Dockerfile` (Python 3.11, CPU-only PyTorch, model baked into the image), `docker-compose.yml` (PostgreSQL 16 with healthcheck, Qdrant, API, named volumes) and `.dockerignore`. The DB password comes from an environment variable, never hard-coded real secrets. `QDRANT_PATH` is set empty in compose because `.env.example` sets it to a folder, which would otherwise override the Qdrant server.

### 3.10 Tests
- `tests/integration/test_end_to_end.py`: 10 tests, upload → extraction → summary → indexing → similarity → search, using the real model and an in-memory Qdrant. Covers reworded queries, one-result-per-document, the extension filter, empty index, bad input, all similarity labels, OCR-needed, reprocessing and listing.
- `tests/test_summarization.py`: 4 unit tests.
- **Result: 118 tests pass** (104 from the teammates + 14 of mine).
- `scripts/evaluate.py` runs the proposal's evaluation on the sample files against a running server.

### 3.11 Docs
`docs/runbook.md` (new), `docs/api-contract.md` (statuses, models and endpoints updated), this report.

## 4. Real evaluation results (`scripts/evaluate.py`, sample files)

Run against both a local server (SQLite + embedded Qdrant) and the **Docker Compose stack (PostgreSQL 16 + Qdrant server + API)**, with identical results. Docker was verified on this Mac using Colima, so `docker-compose` (with a hyphen) was used.

| Check | Result |
|---|---|
| Re-upload of `ai-evolution.pdf` | `exact_duplicate`, 1.000 |
| `ai-evolution-edited.pdf` | `near_duplicate`, 0.997 |
| `ai-milestones.csv` vs paper | `related`, 0.55 |
| `scanned-page.png` | `ocr_needed` |
| "history of artificial intelligence" | AI paper files ranked first |
| "how much money is budgeted" | `project-budget.xlsx` first |

Note: the exact copy and edited copy also appear as separate search results, since they are separate files.

## 5. Problems found in teammates' code (please tell them)

1. **Jahid: first upload fails on an empty Qdrant.** `index_chunks` writes to Qdrant but never creates the collection (`ensure_collection` is only called in search). His tests mock the client so they missed it. I worked around it in my pipeline without editing his file; the cleaner fix is a one-line `ensure_collection(client)` at the top of `index_chunks`.
2. **Jahid: `related` threshold 0.75 is too high** for this model (see 3.6). The threshold is now configurable.
3. **Jahid: `requirements.txt` had no version pins and no trailing newline**; I merged it into one organised file.
4. **Diya: `storage_bridge` calls `get_storage()` directly** instead of using the FastAPI dependency, so test storage overrides do not reach it. Harmless in production; tests must patch `app.extraction.storage_bridge.get_storage`.
5. **Diya: scanned files were marked `failed`.** The proposal wants "needs OCR", so I added `ocr_needed` and the pipeline applies it.

## 6. Known limitations (be honest about these in the demo)

- No real OCR yet; scanned files are only flagged.
- Summaries are extractive, not written by an LLM.
- Thresholds were tuned on 8 small sample files.
- Embedded-Qdrant mode (no Docker) allows only one running server process.
- A single large document makes the near-duplicate check do one Qdrant query per chunk.
- No authentication on the API (out of scope for the proposal).
- Because processing is a background task inside the API process, a server crash mid-processing leaves a file in `extracting`/`indexing`; re-run with `POST /files/{id}/process`.

## 7. Files I added or changed

New: `app/pipeline/`, `app/search/`, `app/summarization/`, `tests/integration/`, `tests/test_summarization.py`, `scripts/evaluate.py`, `Dockerfile`, `docker-compose.yml`, `.dockerignore`, `docs/runbook.md`, this report.
Changed: `app/main.py` (routers, health), `app/ingestion/routes.py` (background task), `app/shared/config/settings.py` (new settings with defaults), `app/shared/models/file.py` (`ocr_needed` status), `app/shared/models/__init__.py` and `requirements.txt` (merge), `tests/conftest.py` (auto-processing off for ingestion tests), `.env.example`, `docs/api-contract.md`.

## 8. How to demo it (5 minutes)

1. `docker compose up --build`, open <http://localhost:8000/docs>.
2. Upload `ai-evolution.pdf`, then `GET /files/{id}` until `indexed`.
3. Upload it again → `is_exact_duplicate: true`; open `/files/{id}/similar`.
4. Upload `ai-evolution-edited.pdf` → `near_duplicate`.
5. Search "when were neural networks invented" (no filename words) → the paper is first, with summary and excerpt.
6. Upload `scanned-page.png` → `ocr_needed`.
