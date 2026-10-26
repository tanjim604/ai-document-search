"""
FastAPI application entry point.

Owner: Tanjim (integration). Wires the ingestion, pipeline and search routers.

Run from the repository root:
    uvicorn app.main:app --reload
Then open http://127.0.0.1:8000/docs
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.ingestion.routes import router as ingestion_router
from app.pipeline.routes import router as pipeline_router
from app.search.routes import router as search_router
from app.shared.database import init_db


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()  # create missing tables when the server starts
    yield


app = FastAPI(title="AI Document Search", lifespan=lifespan)
app.include_router(ingestion_router)
app.include_router(pipeline_router)
app.include_router(search_router)


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}
