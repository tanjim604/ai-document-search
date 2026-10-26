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

### 3.9b Upload dialog and animations
Choosing files (button, folder or drag and drop) now opens a dialog where each file can be renamed before it is saved. The extension is fixed and shown next to the name; leaving a name unchanged keeps the original, and characters that are illegal in filenames are removed. Unsupported and hidden files are listed as skipped with the reason. While uploading, each row shows a spinner that turns into a drawn checkmark (green), an exact-copy notice (amber) or a shake with the error (red), and a progress bar fills. When it finishes, a large checkmark draws in, the dialog closes by itself if everything succeeded, and the new files slide into the top of the library. Animations are switched off for people who set "reduce motion" in their system.

### 3.9c Images and scanned documents (`app/vision/`)
Photos can be anything, such as a meeting or a dog, and a photo has no text for the extraction module to read, so it used to be flagged `ocr_needed` and left unsearchable. Extraction still reports that, and the pipeline now reads these files itself (`app/pipeline/vision_step.py`) and then saves the result exactly like normal extraction, so summaries, embeddings and search need no special cases:

- **What the picture shows:** the BLIP captioning model (`Salesforce/blip-image-captioning-base`, local and free) produces a description that is stored as "This image shows ...". Captions that are mostly punctuation (the model rambles on pictures of plain text) are discarded.
- **Writing in the picture:** Tesseract OCR reads slides, whiteboards and receipts, and every page of a scanned PDF (up to 30 pages). Output with fewer than 10 letters or digits is treated as noise.
- **Search and display:** the library and search results show a small preview of each photo. A file only stays `ocr_needed` if nothing at all could be read.

Each tool is optional, so one failing does not block the other. Results in the Docker stack with real photos: a Labrador photo became "a small dog standing in the grass" and was found by "picture of a dog" (94%); a COCO photo became "two cats sleeping on a couch" and was found by "photo of two cats on a sofa" (100%); a generated meeting-agenda image had its text read by OCR and was found by "show me the meeting agenda image" (91%) and "which file mentions the Q4 budget review" (78%); the scanned sample page from the original samples is now read and indexed. The captioning model is small, so descriptions are short and generic (it called the Labrador a "small dog"), and it can miss detail.

The library also held 22 of my own phone photos (`IMG_*.jpeg`) that had been uploaded before this feature existed and were stuck at `ocr_needed`. I reprocessed all 22 through `POST /files/{id}/process`: 22 of 22 were indexed, at 3 to 7 seconds each, and the library then showed 93 files, all `indexed`. Searching by description found the right photo first: "my dog at the beach" (100%), "photos of food" (89%), "CN tower in Toronto" (100%), "a horse and carriage" (100%) and "boats in a harbor" (100%); generic queries such as "inside of a car" scored lower (47%) because the descriptions give little to match on.

### 3.9d Access protection
The app had no login, so sharing a public link would have let anyone upload files to my machine. I added an optional shared password: when `APP_PASSWORD` is set (in `.env`, which git ignores, or as an environment variable), a middleware asks for it on every page and endpoint except `/health`. The browser shows its own login box (any username, the shared password) and then sends the credentials with each request, so the page's own requests, downloads and photo previews keep working. Comparison uses `secrets.compare_digest`. Without the variable the app stays open for local development. `docker-compose.yml` passes the variable through. The tests clear it so a local `.env` cannot lock them out. I verified on the Docker stack that a request without the password gets 401, with the password 200, and that all stored files were unaffected.

### 3.9e Sharing the system for remote checking
Friends and the supervisor need to check the system from their own machines. Vercel and GitHub Pages cannot run this backend (PyTorch, PostgreSQL and Qdrant do not fit serverless functions, and Pages serves static files only), so I used two options that run the real Docker stack:

- **Temporary public link:** `cloudflared tunnel --url http://localhost:8000` exposes the local app at a random `trycloudflare.com` address for as long as the command runs. I started it from my own terminal, with the password above enabled. The link changes each time and stops when the terminal closes or the Mac sleeps.
- **GitHub Codespaces:** `.devcontainer/devcontainer.json` and `scripts/codespace_start.sh` start the Docker Compose stack in a codespace and load the sample documents. I have not been able to test this one.

A permanent deployment would need a host that runs containers (Render, Railway or Fly.io) with about 1 to 2 GB of memory, which is normally a paid plan; I did not set one up.

### 3.10 Docker
`Dockerfile` (Python 3.11, Tesseract from `apt`, CPU-only PyTorch, the embedding and image captioning models baked into the image), `docker-compose.yml` (PostgreSQL 16 with a healthcheck, Qdrant, the API, named volumes) and `.dockerignore`. The database password comes from an environment variable. `QDRANT_PATH` is set to empty in compose because `.env.example` sets it to a folder, which would otherwise override the Qdrant server.

### 3.11 Tests
- `tests/integration/test_end_to_end.py` (19 tests): upload → extraction → summary → indexing → similarity → search with the real model and an in-memory Qdrant. It covers reworded and chat-style queries, filename matching, one result per document, the extension filter, an empty index, invalid input, every similarity label, photos described and found by what they show, unreadable images, reprocessing, the file list, download, the served web page, five simultaneous uploads, the job queue and resuming unfinished files after a restart.
- Unit tests: `tests/test_summarization.py` (6), `tests/test_query_cleaning.py` (5), `tests/test_ranking.py` (5), `tests/test_vision.py` (11) and `tests/test_auth.py` (3).
- **Result: 153 tests, 152 pass and 1 is skipped** (49 of them are mine, 104 are the teammates'). The skipped test needs Tesseract installed on the host. I could not install it on my Mac because the Xcode Command Line Tools are too old for Homebrew's source build, so OCR was verified inside the Docker image instead.
- `scripts/evaluate.py` runs the proposal's evaluation on the sample files against a running server.

### 3.12 Documentation
`docs/runbook.md` (new), `docs/api-contract.md` (statuses, models and endpoints updated), `README.md`, and this report.

## 4. Problems found and fixed during integration

1. **First upload failed on an empty Qdrant.** `index_chunks` writes to Qdrant but never creates the collection (`ensure_collection` was only called during search). The unit tests mock the client, so they missed it. My pipeline now calls `ensure_collection` before indexing.
2. **Process crash when several files were uploaded at once.** The web page uploads files in parallel. Each upload started its own background thread, all of them loaded the embedding model at once, and Python aborted inside PyTorch. I reproduced it with a test, then fixed it in three places: a lock around every model call in `app/ai_indexing/embeddings.py`, a lock so pipeline jobs take turns writing to Qdrant, and loading the model when the server starts. The same crash could occur when a search ran during indexing; the model lock covers that case too. A later large-batch test exposed a second problem with the same design (connection exhaustion), which the job queue in section 3.9a fixed.
3. **"Related" threshold too high for the model** (section 3.6). It is now configurable.
4. **Scanned files were marked `failed`.** The proposal calls for "needs OCR", so I added the `ocr_needed` status and the pipeline applies it. That left photos and scans unsearchable, which section 3.9c fixed by actually reading them.
5. **Extraction reads storage directly.** `storage_bridge` calls `get_storage()` instead of using the FastAPI dependency, so test storage overrides do not reach it. This is harmless in production, and the end-to-end tests patch it.
6. **`requirements.txt`** had unpinned entries and no trailing newline; it is now one organised file.
7. **The captioning model rambled on pictures of plain text** (for example `a page that reads ' ' ' ', ' '`). I added a check that discards captions that are mostly punctuation; OCR still reads the text.
8. **A local password locked the tests out.** After I set `APP_PASSWORD` in my `.env`, every test request returned 401. The test setup now clears the variable for each test.

Edits to other members' files, for the record: `app/ingestion/routes.py` (background task), `app/shared/config/settings.py` (new settings with defaults), `app/shared/models/file.py` (`ocr_needed` status), `app/ai_indexing/embeddings.py` (model lock).

## 5. Results

I ran `scripts/evaluate.py` against a local server (SQLite and embedded Qdrant) and against the Docker Compose stack (PostgreSQL 16, Qdrant server and API). Both runs gave the same labels.

| Check | Result |
|---|---|
| Re-upload of `ai-evolution.pdf` | `exact_duplicate`, 1.000 |
| `ai-evolution-edited.pdf` | `near_duplicate`, 0.997 |
| `ai-milestones.csv` vs. the paper | `related`, 0.55 |
| `scanned-page.png` (original sample) | now read by OCR and indexed |
| "Pull up the research paper about AI evolution" | `ai-evolution.pdf` ranked first (46%) |
| "history of artificial intelligence" | AI paper files ranked first |
| "how much money is budgeted" | `project-budget.xlsx` ranked first |
| 51 files uploaded in one batch | 51 indexed in 7.4 s, no errors |
| 22 stuck phone photos reprocessed | 22 of 22 indexed; library at 93 files, all `indexed` |
| "my dog at the beach" | `IMG_8443.jpeg` ranked first (100%) |
| "show me the meeting agenda image" | `meeting-agenda.png` ranked first (91%), text read by OCR |
| Request without the password | HTTP 401; with the password HTTP 200 |

The exact copy and the edited copy also appear as separate search results because they are separate files. Docker was run on my Mac with Colima, so the commands used `docker-compose`.

## 6. Limitations

- Photo descriptions come from a small captioning model, so they are short and sometimes imprecise; OCR works best on clean, horizontal printed text and is weaker on handwriting.
- Summaries are extractive, not written by a language model.
- Thresholds were tuned on 8 small sample files and could shift with more varied documents.
- Embedded-Qdrant mode (no Docker) allows only one running server process.
- The near-duplicate check runs one Qdrant query per chunk, so very large documents are slower to compare.
- Files are processed one at a time, so a very large batch takes a while to finish (about 0.15 seconds per small file here).
- Processing runs inside the API process; unfinished files are re-queued when the server restarts.
- Access control is one shared password with no per-user accounts, and there is no delete function.
- OCR was verified only inside Docker (Tesseract could not be installed on my Mac).
- The Codespaces setup is untested, and the tunnel link is temporary.
- Photos are described once at upload; reprocessing is manual (`POST /files/{id}/process`) after changing the vision models.

## 7. Files added or changed

New: `app/pipeline/` (including `vision_step.py`), `app/search/`, `app/summarization/`, `app/vision/`, `app/static/index.html`, `tests/integration/`, `tests/test_summarization.py`, `tests/test_query_cleaning.py`, `tests/test_ranking.py`, `tests/test_vision.py`, `tests/test_auth.py`, `scripts/evaluate.py`, `scripts/bulk_upload.py`, `scripts/generate_samples.py`, `scripts/codespace_start.sh`, `sample_files/library/`, `.devcontainer/`, `Dockerfile`, `docker-compose.yml`, `.dockerignore`, `docs/runbook.md`, this report.
Changed: `app/main.py`, `app/ingestion/routes.py`, `app/shared/config/settings.py`, `app/shared/models/file.py`, `app/shared/models/__init__.py`, `app/ai_indexing/embeddings.py`, `requirements.txt`, `tests/conftest.py`, `.env.example`, `docs/api-contract.md`, `README.md`.

## 8. Running and demonstrating the system

1. `docker compose up --build`, then open <http://localhost:8000> (enter the password if `APP_PASSWORD` is set).
2. Click Upload files, optionally rename `ai-evolution.pdf` in the dialog, and watch the checkmark animation and the status change to Ready.
3. Upload it again: a notice reports the exact copy. Click Related files on either copy.
4. Upload `ai-evolution-edited.pdf`: it appears as a near duplicate.
5. Type "Pull up the research paper about AI evolution": the paper is the first result, with its summary and the matching excerpt.
6. Upload a photo, for example of a dog: its description appears as the summary, and searching "picture of a dog" returns it with a preview.
7. Upload an image containing text, such as `meeting-agenda-slide.png`: OCR reads the writing, and searching for something written in it finds the image.
