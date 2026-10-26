# Runbook: starting, testing and using the system

Owner: Tanjim (integration). Written so that any team member can run everything from these commands.

## 1. Start everything with Docker (PostgreSQL + Qdrant + API)

```bash
cp .env.example .env          # optional; set POSTGRES_PASSWORD here, never commit .env
docker compose up --build     # first build downloads PyTorch and the model (several minutes)
```

- Web app (upload, library, search box): <http://localhost:8000>
- API and interactive docs: <http://localhost:8000/docs>
- Health check: `curl localhost:8000/health`
- Stop: `Ctrl+C`, then `docker compose down` (add `-v` to also delete stored data)

Uploaded originals, PostgreSQL data and the Qdrant index live in Docker volumes, so they survive restarts.

> On a Mac without Docker Desktop: `brew install colima docker docker-compose && colima start`, then use `docker-compose` instead of `docker compose`.

## 1a. Where the data is stored

In the Docker setup everything is kept in the database container, so one place holds it all:

| What | Where |
|---|---|
| Uploaded files (the original PDFs, photos and so on) | PostgreSQL, table `stored_files` |
| File records, extracted text, summaries, duplicate links | PostgreSQL, tables `files`, `document_contents`, `document_chunks`, `similarity_matches` |
| Search index (meaning-numbers) | Qdrant (can be rebuilt from the stored text) |

Browse the database in a web page (Adminer, optional and for this computer only):
`docker-compose --profile tools up -d adminer`, then open <http://localhost:8080> and log in with System `PostgreSQL`, Server `postgres`, Username `ai_docs`, Password `ai_docs` (or your `POSTGRES_PASSWORD`), Database `ai_docs`. The Server box is pre-filled with `postgres`; if you ever see `db` there, change it to `postgres`. Click a table to see its rows. In `stored_files`, the `data` column shows a link such as "1,521 bytes": clicking it downloads the original file (the browser names it `...data`, so rename it back to `.pdf` or the right extension). Stop it with `docker-compose stop adminer`.

Or look inside the database from a terminal (PostgreSQL and Qdrant are reachable from this computer only, not from the network):
`docker-compose exec postgres psql -U ai_docs -d ai_docs` opens a prompt (`\dt` lists tables, `\q` quits). A desktop client such as TablePlus, DBeaver or pgAdmin can connect to host `localhost`, port `5432`, database `ai_docs`, user `ai_docs` and the password from `POSTGRES_PASSWORD` (default `ai_docs`).
The file contents are in `stored_files.data` as binary, so a query shows bytes rather than a readable document. To save one back to a normal file:
`docker-compose exec -T postgres psql -U ai_docs -d ai_docs -Atc "select encode(s.data,'base64') from stored_files s join files f on f.storage_path=s.path where f.filename='report.pdf'" | base64 -d > report.pdf`

Back up the files and all their details with one command:
`docker-compose exec postgres pg_dump -U ai_docs ai_docs > backup.sql`

Data lives in Docker volumes and survives restarts; `docker-compose down -v` deletes it all.

Files uploaded before the switch to database storage can be moved in (safe to repeat; each copy is checked against the file's SHA-256 before the record is updated):
`docker-compose exec api python -m app.shared.storage.migrate`
Add `--delete-old` to remove the old disk copies afterwards. To go back to plain folders, set `STORAGE_BACKEND=local`.

## 1b. Run it online from GitHub (Codespaces)

GitHub itself cannot host this backend (GitHub Pages serves static files only), but a Codespace can run the whole Docker stack from the repository:

1. On GitHub open the repository, then **Code > Codespaces > Create codespace on feature/search-integration** (or `main` after merging).
2. Wait a few minutes: `.devcontainer/devcontainer.json` starts Docker Compose and loads the sample documents.
3. Open the **Ports** tab and click the globe icon next to port 8000. To share the link, right-click the port and set **Port Visibility > Public**.

A codespace stops after inactivity (the free personal allowance is limited), so this suits demos rather than permanent hosting. For a permanent site, deploy the same `Dockerfile` and `docker-compose.yml` to a host that runs containers (Render, Railway or Fly.io); Vercel cannot run it because PyTorch, PostgreSQL and Qdrant do not fit its serverless functions.

## 1c. Share a temporary link with friends or a professor (free)

Run this on the machine where the stack is running. It needs no account and exposes your local app through a random public address for as long as the command runs.

1. Set a password so strangers cannot upload to your machine: put `APP_PASSWORD=choose-something` in `.env`, then `docker compose up -d` (the page asks for it; any username works).
2. `brew install cloudflared` (once), then `cloudflared tunnel --url http://localhost:8000`.
3. Send the `https://....trycloudflare.com` address from the output, plus the password.

The link changes every time you start the tunnel, and it stops working when you close the command or the Mac sleeps.

## 2. Run without Docker (quick local development)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` to use files instead of servers:

```
DATABASE_URL=sqlite:///data/dev.db
QDRANT_PATH=data/qdrant        # embedded Qdrant, no server needed
```

```bash
uvicorn app.main:app --reload
```

## 3. Use it

**Photos and scans.** Any PNG or JPEG is read automatically: a captioning model describes what the picture shows (for example "a dog standing in the grass" or "a group of people sitting around a table") and Tesseract OCR reads any writing in it, so you can find a photo by describing it ("picture of a dog", "the meeting slide with the budget agenda"). Scanned PDFs are read page by page with OCR (first 30 pages). Both need the Docker setup, or Tesseract on your machine for local runs (`brew install tesseract`; the captioning model downloads about 1 GB the first time). Without Tesseract, photos are still described and only the OCR part is skipped.

Easiest: open <http://localhost:8000>, upload files (button or drag and drop), then type what you are looking for, for example `Pull up the research paper about AI evolution`. A link such as `http://localhost:8000/?q=budget` runs a search on load.

Or use the API directly:

```bash
# upload (processing runs in the background)
curl -F "file=@sample_files/ingestion/ai-evolution.pdf" localhost:8000/files

# poll until status is "indexed" (or "ocr_needed" / "failed")
curl localhost:8000/files/<file_id>

# search by meaning
curl "localhost:8000/search?q=history+of+artificial+intelligence"

# duplicates and related files
curl localhost:8000/files/<file_id>/similar
```

Upload a whole folder (all sub-folders, supported types only) and watch it process:

```bash
python scripts/bulk_upload.py sample_files/library http://localhost:8000
```

The web page also has an **Upload folder** button, and you can drop a folder onto the page.

Recreate the 51-file sample library (PDF, DOCX, TXT, CSV, XLSX) in `sample_files/library/`:

```bash
python scripts/generate_samples.py
```

Run the whole evaluation on the original sample files against a running server:

```bash
python scripts/evaluate.py http://localhost:8000
```

## 4. Tests

```bash
pytest                          # everything (about 120 tests)
pytest tests/integration        # end-to-end: upload -> search (real model, in-memory Qdrant)
```

The end-to-end tests load the real embedding model. The first run downloads it (about 90 MB); they skip themselves if it is unavailable.

## 5. Settings (environment variables)

| Variable | Default | Meaning |
|---|---|---|
| `DATABASE_URL` | local PostgreSQL | SQLAlchemy URL |
| `STORAGE_BACKEND` | `local` (`database` in docker-compose) | `database` keeps uploaded files inside PostgreSQL; `local` keeps them in a folder |
| `UPLOAD_DIR` | `data/uploads` | The folder used by `local` storage, and the place old files are read from after switching to `database` |
| `QDRANT_URL` / `QDRANT_PATH` | `http://localhost:6333` / unset | Server URL, or a folder for embedded mode (path wins if set) |
| `AUTO_PROCESS_UPLOADS` | `true` | Process each upload in the background |
| `NEAR_DUPLICATE_THRESHOLD` | `0.95` | Document score at or above this = near duplicate |
| `RELATED_THRESHOLD` | `0.45` | Document score at or above this = related |
| `POSTGRES_PASSWORD` | `ai_docs` | Used by docker compose only |

## 6. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| File stuck at `uploaded` | Files are processed one at a time in the background; large batches take a while. Anything unfinished restarts automatically when the server restarts, or call `POST /files/<id>/process` |
| Status `ocr_needed` | Scanned PDF or image with no text. OCR is not built yet; by design it is not embedded |
| Status `failed` | Call `POST /files/<id>/process`; the response contains the error |
| `Storage folder is already accessed by another instance` | Embedded Qdrant allows one process. Stop the other server, or use the Qdrant container |
| Search returns nothing | Lower `min_score`, or check the file reached `indexed` |
