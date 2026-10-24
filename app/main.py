"""
FastAPI application entry point.

NOTE: Tanjim owns this file (integration). This is the minimal version needed
to run the ingestion module. When Tanjim adds the search router, keep the
ingestion lines below.

Run from the repository root:
    uvicorn app.main:app --reload
Then open http://127.0.0.1:8000/docs
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.ingestion.routes import router as ingestion_router
from app.shared.database import init_db


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()  # create missing tables when the server starts
    yield


app = FastAPI(title="AI Document Search", lifespan=lifespan)
app.include_router(ingestion_router)
