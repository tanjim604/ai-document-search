# API Contract

The shared agreement that lets the four modules connect. It lists the data models, status values, endpoints and handoff rules from the team plan.

**Rule:** change this file (or any model in `app/shared/models/`) only through a pull request that the whole team has seen.

Each owner fills in their own section as they build it. Sections marked *Not built yet* only repeat the fields already agreed in the team plan.

---

## 1. Data models (`app/shared/models/`)

### File · owner: Tahmid · built

Code: `app/shared/models/file.py` · Table: `files` · SQL: [`docs/sql/files_table.sql`](sql/files_table.sql)

| Field | Type | Notes |
|---|---|---|
| `id` | string, primary key | The `file_id` every service uses, e.g. `f_3f2a9c...` |
| `filename` | string | Original name from the upload. **Not unique.** |
| `extension` | string | Lower case, no dot: `pdf`, `docx`, `txt`, `csv`, `xlsx`, `png`, `jpg`, `jpeg` |
| `mime_type` | string | Decided from the file's content, e.g. `application/pdf` |
| `storage_path` | string, unique | e.g. `db/pdf/f_3f2a9c....pdf` (database storage, the Docker default) or `data/uploads/pdf/f_3f2a9c....pdf` (local storage). Always read it through the storage adapter. |
| `sha256_hash` | string (64 hex) | Content fingerprint. The same bytes always give the same hash. |
| `processing_status` | string | See section 2 |
| `created_at` | timestamp with time zone | When the upload was saved |

### DocumentContent · owner: Diya (summary: Tanjim for now) · built

`file_id`, `raw_text`, `summary` (2-3 sentence extractive summary, written by `app/summarization`)

### DocumentChunk · owner: Diya · built

`id`, `file_id`, `chunk_index` (0, 1, 2, ...), `text`

### SimilarityMatch · owner: Zahid · built

`source_file_id`, `matched_file_id`, `similarity_score`, `match_type`

`match_type` is `exact_duplicate` (score `1.0`, same SHA-256), `near_duplicate` or `related`. Near-duplicate and related scores are document-level (see `app/pipeline/similarity.py`); thresholds are settings (`NEAR_DUPLICATE_THRESHOLD` 0.95, `RELATED_THRESHOLD` 0.45). A match is stored once, from the newer file's side.

---

## 2. Processing status

```
uploaded → extracting → extracted → indexing → indexed
                 (any step can go to) failed
```

| Value | Set by | Meaning |
|---|---|---|
| `uploaded` | Tahmid | Original saved and recorded |
| `extracting` | Diya | Extraction started |
| `extracted` | Diya | Text and chunks saved |
| `indexing` | Zahid | Embedding started |
| `indexed` | Zahid | Every chunk is stored in the vector database |
| `ocr_needed` | Tanjim (pipeline) | Scanned PDF or image: no text, so nothing is embedded |
| `failed` | Whoever hit the error | Processing stopped |

The values live in `ProcessingStatus` (`app/shared/models/file.py`). Change a status with:

```python
from app.ingestion.service import update_processing_status
from app.shared.models.file import ProcessingStatus

update_processing_status(db, file_id, ProcessingStatus.EXTRACTED)
```

---

## 3. Endpoints

| Method and path | Purpose | Owner | State |
|---|---|---|---|
| `POST /files` | Upload one file (multipart field `file`) | Tahmid | Built |
| `GET /files/{file_id}` | Status and details of one file | Tahmid | Built |
| `GET /` | Web app (upload, library, search) | Tanjim | Built |
| `GET /files` | List files with status and summary (`limit`, `offset`) | Tanjim | Built |
| `GET /files/{file_id}/download` | The original file | Tanjim | Built |
| `POST /files/{file_id}/process` | Run or re-run extraction, summary, indexing | Tanjim | Built |
| `GET /files/{file_id}/similar` | Duplicate and related-file matches | Tanjim | Built |
| `GET /search?q=...` | Semantic search, one result per document | Tanjim | Built |
| `GET /health` | Liveness check | Tanjim | Built |

### `POST /files` → `201`

```json
{
  "file_id": "f_74a2502cd543454ebcf8b116b8c554e7",
  "filename": "ai-evolution.pdf",
  "extension": "pdf",
  "mime_type": "application/pdf",
  "storage_path": "data/uploads/pdf/f_74a2502cd543454ebcf8b116b8c554e7.pdf",
  "sha256_hash": "ff53469fbf54aa0fde491e21191454f390bdea7b335e8dcfee7875d0995f8406",
  "status": "uploaded",
  "is_exact_duplicate": false,
  "duplicate_of": null
}
```

Errors: `400` empty file / content does not match extension / no filename · `413` too large · `415` type not allowed · `422` no `file` field. Every error body is `{"detail": "<message>"}`.

### `GET /files/{file_id}` → `200`

The same fields as above without the two duplicate fields, plus `created_at`. Unknown ID → `404`.

### `POST /files` after the upload

Unless `AUTO_PROCESS_UPLOADS=false`, the server then runs extraction, summary and indexing in the background. Poll `GET /files/{file_id}` until `status` is `indexed`, `ocr_needed` or `failed`.

### `GET /search?q=...` → `200`

Request words such as "Pull up the" or "Find me a" are removed before matching. Query parameters: `q` (required, 1-500 characters), `limit` (1-50, default 10), `min_score` (0-1, default 0.2), `extension` (e.g. `pdf`). Only `indexed` files are returned; each file appears once with its best-matching chunk. `score` is a calibrated relevance from 0 to 1 (semantic similarity plus a bonus for query words found in the filename, summary or text; see `app/search/ranking.py`), and `semantic_score` is the raw cosine similarity. Results are sorted by `score`.

```json
{ "query": "research paper about AI evolution",
  "results": [{ "file_id": "f_123", "filename": "ai-evolution.pdf", "extension": "pdf",
                "summary": "A paper describing the history and evolution of AI.",
                "score": 0.84, "semantic_score": 0.46, "matched_excerpt": "The development of AI progressed...",
                "storage_path": "data/uploads/pdf/f_123.pdf" }] }
```

### `GET /files/{file_id}/similar` → `200`

```json
{ "file_id": "f_2", "matches": [
  { "file_id": "f_1", "filename": "ai-evolution.pdf", "match_type": "near_duplicate", "score": 0.997 } ] }
```

### `POST /files/{file_id}/process` → `200`

`{"file_id", "status", "error", "chunks", "summary"}`. Unknown ID → `404`.

---

## 4. Handoff rules

1. **One ID everywhere.** Every table, vector payload and API result refers to a file by `file_id`.
2. **Ingestion → Extraction.** Diya gets `file_id`, `storage_path`, `extension`, `filename` and `processing_status` from the `File` row (`get_file(db, file_id)`). She reads the bytes with `get_storage().read_bytes(storage_path)` and never writes to or moves the original.
3. **Extraction → Indexing.** Zahid gets `file_id`, full text, ordered chunks, `filename` and `extension`. Empty or scanned documents get a clear status instead of empty text.
4. **Exact duplicates.** Files with the same `sha256_hash` are identical. `find_files_with_same_hash(db, file_id)` returns the other copies.
5. **Indexing → Search.** Each search hit can be mapped back to `file_id`, `filename`, `extension` and a score.
6. **Secrets.** Settings come from environment variables (`.env`, never committed). Only `.env.example` goes in Git.

Details and examples for the ingestion handoffs: [`docs/ingestion.md`](ingestion.md).
