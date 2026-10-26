# Search and Integration: Work Report

**Author:** Tanjim Sohan · **Branch:** `feature/search-integration` · **Course:** COMP 3710 Applied Artificial Intelligence

This report records my work on the "Search and integration" module: what I built, how it works, the decisions I made, the problems I ran into, and the results I measured.

## 1. Scope

The proposal (sections 7 and 9) assigns me the GitHub setup, the search API, Docker Compose, the end-to-end tests and the documentation, and it makes me responsible for connecting the other three modules into one working system. The proposal listed the UI as out of scope; I added a web interface later in the project (section 3.9) so the system can be used and demonstrated without API tools.

## 2. Starting point

| Module | Branch | State when I started |
|---|---|---|
| Ingestion (Tahmid) | `feature/ingestion-storage` | Complete: upload API, validation, SHA-256 hashing, local storage, tests. |
| Extraction (Diya) | `feature/content-extraction` | Complete: readers for all file types, cleaning, chunking, OCR check, database saving. |
| AI indexing (Jahid) | `feature/ai-indexing-similarity` | Embeddings, Qdrant storage and exact-duplicate records. No summaries and no near-duplicate or related records yet. |
| Search and integration (me) | `feature/search-integration` | Empty (README only). |

No code connected the modules: nothing started extraction after an upload, and nothing started indexing after extraction.

## 3. Work completed

### 3.1 Merging the branches
I merged the three module branches into `feature/search-integration`. Two files conflicted, `app/shared/models/__init__.py` and `requirements.txt`, because each teammate added their own lines. I kept both sides and organised `requirements.txt` by module. After the merge, the teammates' 104 tests all passed.

### 3.2 The pipeline (`app/pipeline/service.py`)
`process_document()` runs one file through every stage using the teammates' existing functions:

1. **Extract** with Diya's `extract_and_save`: text and ordered chunks saved to the database.
2. **Summarize** (mine): summary saved on `DocumentContent.summary`.
3. **Index** with Jahid's `index_document`: chunk vectors stored in Qdrant, exact duplicates recorded.
4. **Compare** (mine): near-duplicate and related matches recorded.

A file with no extractable text (a scanned PDF or an image) gets the new status `ocr_needed` and is not embedded, as the proposal requires. Any other error sets `failed`, and the message is returned instead of crashing the server.

### 3.3 Automatic processing on upload
`POST /files` now schedules the pipeline as a FastAPI background task. The upload returns immediately and the client polls `GET /files/{id}` until the status is `indexed`, `ocr_needed` or `failed`. This required three small edits to Tahmid's `routes.py`. The background job opens its own database session because the request's session is already closed by then. `POST /files/{id}/process` re-runs the pipeline manually.

### 3.4 Summaries (`app/summarization/`)
Jahid planned to add summaries later, so I wrote a local extractive summarizer to fill the gap. It embeds every sentence with the project's existing model and keeps the three sentences closest to the document's average meaning, in their original order. It needs no API key and works offline in Docker. CSV and XLSX files, which have no sentences, get a readable description such as `Table with 5 rows and columns: year, milestone, category.` The summarizer sits behind one function, `summarize_text`, so replacing it with Jahid's version later means changing one file (`app/summarization/__init__.py`).

### 3.5 Similarity labels (`app/pipeline/similarity.py`)
Jahid's `search_similar_files` labels a file by its single best chunk, so two unrelated documents that share one boilerplate paragraph would look like near-duplicates. I score a candidate at document level instead: for each chunk of the new file I take its best match in the candidate, then average over all chunks (0 where nothing matches). Only files that are alike overall score high.

Labels: exact duplicate (same SHA-256, Jahid's code), near duplicate (score at least 0.95), related (score at least 0.45), otherwise nothing is stored.

### 3.6 Threshold tuning
The proposal said the 0.95 near-duplicate threshold would be tuned on real samples. I measured scores with the project's model, `all-MiniLM-L6-v2`:

| Pair | Score |
|---|---|
| Document vs. lightly edited copy | 0.997 |
| Two related AI documents | 0.47 to 0.56 |
| Unrelated (AI vs. cooking) | about 0.02 |

The inherited "related" threshold of 0.75 never fires for related documents with this model. I tried 0.40 first, but the reading-list file was labelled related to the AI paper at 0.42 to 0.43, which looked like a false positive, so I settled on **0.45**. Both thresholds are environment variables. The tuning used only 8 sample files.

### 3.7 Search (`GET /search`, `app/search/`)
1. Strip request words from the prompt ("Pull up the …", "Can you find me a …") so only the subject is embedded.
2. Embed the cleaned query with the same model as the documents.
3. Ask Qdrant for the closest chunks (five times `limit`, so grouping still fills the page).
4. Group by file and keep each file's best chunk: one result per document.
5. Look up filename, storage path and summary in PostgreSQL; skip files that are not `indexed`.
6. Rank with a hybrid score (section 3.7a) and return `file_id, filename, extension, summary, score, semantic_score, matched_excerpt, storage_path`.

Parameters: `q`, `limit`, `min_score` (default 0.2), `extension`.

### 3.7a Hybrid ranking and calibrated relevance (`app/search/ranking.py`)
Raw cosine similarity from `all-MiniLM-L6-v2` is low even for the correct document: typical correct matches scored only 0.34 to 0.55, so the page showed 34 to 46% for files that were exactly right. The model also ignores filenames, and a query for "project proposal for AI document search" ranked the file named `AI_Document_Search_Proposal.pdf` fourth. I made two changes:

1. **Hybrid score.** I add a bonus when the query's keywords appear in the filename (up to 0.25), or in the summary or best-matching text (up to 0.20). Keywords exclude filler words, and a light stemming step lets "evolution" match "evolutionary".
2. **Calibration.** The hybrid score is mapped linearly onto 0 to 100% (0.20 is 0% and 0.90 is 100%). The constants come from the scores I measured, and they live at the top of `ranking.py`.

The calibration is a rescaling of the same signal, not new evidence of relevance, so weak matches stay low. Results are sorted by the new score, and the response also carries the raw `semantic_score`. Measured on the 59-file library: all 11 test queries returned the right file first, with correct matches at 61 to 100% and unrelated files at 1 to 20%. The proposal query now ranks `AI_Document_Search_Proposal.pdf` first (94%).

### 3.8 Other endpoints
`GET /files` (list with status and summary), `GET /files/{id}/similar`, `GET /files/{id}/download` (the original file), `POST /files/{id}/process`, `GET /health`.

### 3.9 Web interface (`app/static/index.html`)
A single self-contained page served at `/` by the API, with no build step and no external dependencies, so it works inside Docker and offline.

- **Library panel:** every uploaded file with a type tile, status badge (Ready, Processing, Needs OCR, Failed), upload date and its summary, plus Open, Full summary, Related files and Retry actions. A filter box searches names and summaries.
- **Ask box:** a ChatGPT-style prompt at the bottom. I type "Pull up the research paper about AI evolution" and the answer lists the matching documents best first, each with a match-strength label, summary, highlighted excerpt, an Open file button and a Show in library button. Example prompts on the empty screen start a search with one click.
- **Upload:** an Upload button, plus drag and drop anywhere on the page. Several files can be uploaded at once. Processing files update their status automatically. Uploading an exact copy shows a notice naming the original.
- **Layout:** light and dark themes follow the system setting, and on narrow screens the page switches to Ask and Library tabs.
- `/?q=...` runs a search on load.

I checked the page by running the real server with the sample files and taking headless-browser screenshots of the home screen, the search answer and a narrow window.

### 3.9a Large uploads
The first version started one background thread per upload. When 50 files were uploaded at once, the waiting threads used up the server's worker threads and held database connections, the connection pool ran out and uploads failed with HTTP 500. I replaced it with a single job queue and one worker thread (`app/pipeline/dependencies.py`): an upload only adds the file id to the queue and returns, and the worker processes files in order. Files left unfinished by a restart or crash are queued again when the server starts. The page uploads four files at a time, shows a progress bar, skips hidden and unsupported files, lists every file that could not be uploaded with the reason, and can upload a whole folder (button or drag and drop). `scripts/bulk_upload.py` does the same from the command line.

I generated a 51-file sample library (`scripts/generate_samples.py`, output in `sample_files/library/`: 16 PDF, 10 DOCX, 16 TXT, 5 CSV, 4 XLSX, covering AI, science, history, cooking, finance, travel and office documents, with one exact duplicate and one near duplicate). Uploaded together with the 8 original samples, 58 of 59 files were indexed (the other is the scanned PNG, flagged `ocr_needed`, and the one fake PDF in the original samples is correctly rejected). The 51-file batch uploaded in 1.3 seconds and finished indexing in 7.4 seconds.

### 3.10 Docker
`Dockerfile` (Python 3.11, CPU-only PyTorch, embedding model baked into the image), `docker-compose.yml` (PostgreSQL 16 with a healthcheck, Qdrant, the API, named volumes) and `.dockerignore`. The database password comes from an environment variable. `QDRANT_PATH` is set to empty in compose because `.env.example` sets it to a folder, which would otherwise override the Qdrant server.

### 3.11 Tests
- `tests/integration/test_end_to_end.py` (17 tests): upload → extraction → summary → indexing → similarity → search with the real model and an in-memory Qdrant. It covers reworded and chat-style queries, one result per document, the extension filter, an empty index, invalid input, every similarity label, OCR-needed files, reprocessing, the file list, download, the served web page, and five simultaneous uploads.
- `tests/test_summarization.py` (6 tests) and `tests/test_query_cleaning.py` (5 tests) and `tests/test_ranking.py` (5 tests).
- **Result: 137 tests pass.**
- `scripts/evaluate.py` runs the proposal's evaluation on the sample files against a running server.

### 3.12 Documentation
`docs/runbook.md` (new), `docs/api-contract.md` (statuses, models and endpoints updated), `README.md`, and this report.

## 4. Problems found and fixed during integration

1. **First upload failed on an empty Qdrant.** `index_chunks` writes to Qdrant but never creates the collection (`ensure_collection` was only called during search). The unit tests mock the client, so they missed it. My pipeline now calls `ensure_collection` before indexing.
2. **Process crash when several files were uploaded at once.** The web page uploads files in parallel. Each upload started its own background thread, all of them loaded the embedding model at once, and Python aborted inside PyTorch. I reproduced it with a test, then fixed it in three places: a lock around every model call in `app/ai_indexing/embeddings.py`, a lock so pipeline jobs take turns writing to Qdrant, and loading the model when the server starts. The same crash could occur when a search ran during indexing; the model lock covers that case too. A later large-batch test exposed a second problem with the same design (connection exhaustion), which the job queue in section 3.9a fixed.
3. **"Related" threshold too high for the model** (section 3.6). It is now configurable.
4. **Scanned files were marked `failed`.** The proposal calls for "needs OCR", so I added the `ocr_needed` status and the pipeline applies it.
5. **Extraction reads storage directly.** `storage_bridge` calls `get_storage()` instead of using the FastAPI dependency, so test storage overrides do not reach it. This is harmless in production, and the end-to-end tests patch it.
6. **`requirements.txt`** had unpinned entries and no trailing newline; it is now one organised file.

Edits to other members' files, for the record: `app/ingestion/routes.py` (background task), `app/shared/config/settings.py` (new settings with defaults), `app/shared/models/file.py` (`ocr_needed` status), `app/ai_indexing/embeddings.py` (model lock).

## 5. Results

I ran `scripts/evaluate.py` against a local server (SQLite and embedded Qdrant) and against the Docker Compose stack (PostgreSQL 16, Qdrant server and API). Both runs gave the same labels.

| Check | Result |
|---|---|
| Re-upload of `ai-evolution.pdf` | `exact_duplicate`, 1.000 |
| `ai-evolution-edited.pdf` | `near_duplicate`, 0.997 |
| `ai-milestones.csv` vs. the paper | `related`, 0.55 |
| `scanned-page.png` | `ocr_needed` |
| "Pull up the research paper about AI evolution" | `ai-evolution.pdf` ranked first (46%) |
| "history of artificial intelligence" | AI paper files ranked first |
| "how much money is budgeted" | `project-budget.xlsx` ranked first |
| 51 files uploaded in one batch | 51 indexed in 7.4 s, no errors |

The exact copy and the edited copy also appear as separate search results because they are separate files. Docker was run on my Mac with Colima, so the commands used `docker-compose`.

## 6. Limitations

- No real OCR yet; scanned files are only flagged.
- Summaries are extractive, not written by a language model.
- Thresholds were tuned on 8 small sample files and could shift with more varied documents.
- Embedded-Qdrant mode (no Docker) allows only one running server process.
- The near-duplicate check runs one Qdrant query per chunk, so very large documents are slower to compare.
- Files are processed one at a time, so a very large batch takes a while to finish (about 0.15 seconds per small file here).
- Processing runs inside the API process; unfinished files are re-queued when the server restarts.
- The API and web page have no authentication or delete function.

## 7. Files added or changed

New: `app/pipeline/`, `app/search/`, `app/summarization/`, `app/static/index.html`, `tests/integration/`, `tests/test_summarization.py`, `tests/test_query_cleaning.py`, `scripts/evaluate.py`, `Dockerfile`, `docker-compose.yml`, `.dockerignore`, `docs/runbook.md`, this report.
Changed: `app/main.py`, `app/ingestion/routes.py`, `app/shared/config/settings.py`, `app/shared/models/file.py`, `app/shared/models/__init__.py`, `app/ai_indexing/embeddings.py`, `requirements.txt`, `tests/conftest.py`, `.env.example`, `docs/api-contract.md`, `README.md`.

## 8. Running and demonstrating the system

1. `docker compose up --build`, then open <http://localhost:8000>.
2. Upload `ai-evolution.pdf` and watch its status change to Ready.
3. Upload it again: a notice reports the exact copy. Click Related files on either copy.
4. Upload `ai-evolution-edited.pdf`: it appears as a near duplicate.
5. Type "Pull up the research paper about AI evolution": the paper is the first result, with its summary and the matching excerpt.
6. Upload `scanned-page.png`: it is marked Needs OCR and is not searchable.

## 9. AI tool use

I used an AI coding assistant (Claude Code) to help implement and document this module, consistent with the AI tool acknowledgement in the project proposal.
