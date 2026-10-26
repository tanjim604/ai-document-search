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

## 1b. Run it online from GitHub (Codespaces)

GitHub itself cannot host this backend (GitHub Pages serves static files only), but a Codespace can run the whole Docker stack from the repository:

1. On GitHub open the repository, then **Code > Codespaces > Create codespace on feature/search-integration** (or `main` after merging).
2. Wait a few minutes: `.devcontainer/devcontainer.json` starts Docker Compose and loads the sample documents.
3. Open the **Ports** tab and click the globe icon next to port 8000. To share the link, right-click the port and set **Port Visibility > Public**.

A codespace stops after inactivity (the free personal allowance is limited), so this suits demos rather than permanent hosting. For a permanent site, deploy the same `Dockerfile` and `docker-compose.yml` to a host that runs containers (Render, Railway or Fly.io); Vercel cannot run it because PyTorch, PostgreSQL and Qdrant do not fit its serverless functions.

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
| `UPLOAD_DIR` | `data/uploads` | Where originals are stored |
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
