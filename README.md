# ai-document-search

AI-powered document storage, semantic search, and duplicate detection (COMP 3710 final project).

Upload PDF, DOCX, TXT, CSV or XLSX files. The backend extracts and chunks the text, writes a summary,
indexes embeddings in Qdrant, labels exact duplicates, near duplicates and related files, and lets you
search by meaning instead of filename.

```bash
docker compose up --build      # PostgreSQL + Qdrant + API
# then open http://localhost:8000 (web app) or http://localhost:8000/docs (API)
```

| Module | Owner | Code |
|---|---|---|
| Ingestion and storage | Tahmid | `app/ingestion`, `app/shared` |
| Content extraction | Diya | `app/extraction` |
| AI indexing and similarity | Jahid | `app/ai_indexing` |
| Search, pipeline, Docker, docs | Tanjim | `app/search`, `app/pipeline`, `app/summarization` |

Docs: [runbook](docs/runbook.md) · [API contract](docs/api-contract.md) · [integration report](docs/search-integration-report.md)
