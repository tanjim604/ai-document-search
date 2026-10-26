"""
FastAPI application entry point.

Owner: Tanjim (integration). Wires the ingestion, pipeline and search routers.

Run from the repository root:
    uvicorn app.main:app --reload
Then open http://127.0.0.1:8000/docs
"""
import base64
import os
import secrets
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, Response

from app.ingestion.routes import router as ingestion_router
from app.pipeline.dependencies import resume_unfinished
from app.pipeline.routes import router as pipeline_router
from app.search.routes import router as search_router
from app.shared.config.settings import get_settings
from app.shared.database import init_db


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()  # create missing tables when the server starts
    from app.ai_indexing.embeddings import get_model

    get_model()  # load the embedding model now, not during the first upload or search
    if get_settings().auto_process:
        resume_unfinished()  # finish files that a restart or crash left half-processed
    yield


app = FastAPI(title="AI Document Search", lifespan=lifespan)


@app.middleware("http")
async def require_password(request: Request, call_next):
    """If APP_PASSWORD is set, every page and endpoint (except /health) asks for it.

    The browser shows its own login box (any username, the shared password) and then
    sends it with every request. Leave APP_PASSWORD unset for local development.
    """
    password = os.getenv("APP_PASSWORD")
    if password and request.url.path != "/health":
        try:
            given = base64.b64decode(request.headers.get("authorization", "")[6:]).decode().partition(":")[2]
        except Exception:
            given = ""
        if not secrets.compare_digest(given.encode(), password.encode()):
            return Response("Password required", 401, headers={"WWW-Authenticate": 'Basic realm="AI Document Search"'})
    return await call_next(request)


app.include_router(ingestion_router)
app.include_router(pipeline_router)
app.include_router(search_router)


@app.get("/", include_in_schema=False)
def web_app() -> FileResponse:
    return FileResponse(Path(__file__).parent / "static" / "index.html")


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}
