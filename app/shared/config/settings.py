"""
Shared project settings, read from environment variables.

In development the values come from a `.env` file in the repository root
(copy `.env.example` to `.env`). Real environment variables always win over
the `.env` file, which is how Docker Compose and the test suite override them.

Owner of the ingestion settings below: Tahmid.
Other members can add their own settings to the same Settings class.
"""
import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()  # does nothing if there is no .env file


@dataclass(frozen=True)
class Settings:
    # PostgreSQL connection string, e.g.
    # postgresql+psycopg2://ai_docs:ai_docs@localhost:5432/ai_docs
    database_url: str

    # Folder where original uploaded files are saved (local storage).
    upload_dir: str

    # Largest file POST /files will accept, in bytes.
    max_upload_size_bytes: int

    # Which storage adapter to use. Only "local" exists for now;
    # a cloud adapter (S3 / Azure Blob / Google Cloud Storage) can be added later.
    storage_backend: str


def load_settings() -> Settings:
    max_mb = int(os.getenv("MAX_UPLOAD_SIZE_MB", "25"))
    return Settings(
        database_url=os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg2://ai_docs:ai_docs@localhost:5432/ai_docs",
        ),
        upload_dir=os.getenv("UPLOAD_DIR", "data/uploads"),
        max_upload_size_bytes=max_mb * 1024 * 1024,
        storage_backend=os.getenv("STORAGE_BACKEND", "local"),
    )


@lru_cache
def get_settings() -> Settings:
    """Return one shared Settings object (FastAPI dependency)."""
    return load_settings()
