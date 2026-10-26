"""
Storage adapters for original uploaded files.

Everyone should get the storage object like this:

    from app.shared.storage import get_storage
    storage = get_storage()
    data = storage.read_bytes(file.storage_path)
"""
from functools import lru_cache

from app.shared.config.settings import get_settings
from app.shared.storage.base import StorageBackend
from app.shared.storage.database import DatabaseStorage
from app.shared.storage.local import LocalStorage


@lru_cache
def get_storage() -> StorageBackend:
    """Return the storage adapter chosen by STORAGE_BACKEND (FastAPI dependency)."""
    settings = get_settings()
    if settings.storage_backend == "local":
        return LocalStorage(settings.upload_dir)
    if settings.storage_backend == "database":
        from app.shared.database import get_session_factory

        # Files saved before the switch stay readable from the old upload folder.
        return DatabaseStorage(get_session_factory(), fallback=LocalStorage(settings.upload_dir))
    raise ValueError(
        f"Unknown STORAGE_BACKEND '{settings.storage_backend}'. Use 'local' or 'database'."
    )


__all__ = ["StorageBackend", "LocalStorage", "DatabaseStorage", "get_storage"]
