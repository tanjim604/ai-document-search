"""
Database storage adapter (Tanjim): uploaded files live inside the database.

The bytes go into the `stored_files` table next to the rest of the data, so one
database holds every file together with its metadata, text and summary, and one
database backup covers all of it. Paths look like `db/pdf/f_3f2a9c....pdf`.

Files saved earlier by the local-disk adapter keep working: any path that does not
start with `db/` is passed to the `fallback` adapter until it is moved with
`python -m app.shared.storage.migrate`.
"""
from typing import Callable

from sqlalchemy.orm import Session

from app.shared.models.stored_file import StoredFile
from app.shared.storage.base import StorageBackend

PREFIX = "db/"


class DatabaseStorage(StorageBackend):
    def __init__(self, session_factory: Callable[[], Session], fallback: StorageBackend | None = None):
        self._session_factory = session_factory
        self._fallback = fallback

    @staticmethod
    def is_database_path(storage_path: str) -> bool:
        return storage_path.startswith(PREFIX)

    def save(self, file_id: str, extension: str, data: bytes) -> str:
        path = f"{PREFIX}{extension}/{file_id}.{extension}"
        with self._session_factory() as db:
            if db.get(StoredFile, path) is not None:  # same rule as local storage: never overwrite
                raise FileExistsError(path)
            db.add(StoredFile(path=path, data=data, size_bytes=len(data)))
            db.commit()
        return path

    def read_bytes(self, storage_path: str) -> bytes:
        if not self.is_database_path(storage_path):
            return self._legacy().read_bytes(storage_path)
        with self._session_factory() as db:
            row = db.get(StoredFile, storage_path)
            if row is None:
                raise FileNotFoundError(storage_path)
            return row.data

    def exists(self, storage_path: str) -> bool:
        if not self.is_database_path(storage_path):
            return self._legacy().exists(storage_path)
        with self._session_factory() as db:
            return db.get(StoredFile, storage_path) is not None

    def delete(self, storage_path: str) -> None:
        if not self.is_database_path(storage_path):
            return self._legacy().delete(storage_path)
        with self._session_factory() as db:
            row = db.get(StoredFile, storage_path)
            if row is not None:
                db.delete(row)
                db.commit()

    def _legacy(self) -> StorageBackend:
        if self._fallback is None:
            raise FileNotFoundError("This file is on local disk and no local storage is configured.")
        return self._fallback
