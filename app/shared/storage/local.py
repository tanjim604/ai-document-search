"""
Local-disk storage adapter.

Files are sorted into one folder per extension, and named by file_id
(never by the user's filename):

    data/uploads/
        pdf/f_3f2a9c....pdf
        docx/f_81b0de....docx
        txt/f_77c1aa....txt
"""
from pathlib import Path

from app.shared.storage.base import StorageBackend


class LocalStorage(StorageBackend):
    def __init__(self, root: str | Path):
        self.root = Path(root)

    def save(self, file_id: str, extension: str, data: bytes) -> str:
        folder = self.root / extension
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{file_id}.{extension}"
        # "xb" = create a new file and fail if one already exists,
        # so an existing upload can never be overwritten.
        with open(path, "xb") as f:
            f.write(data)
        return path.as_posix()

    def read_bytes(self, storage_path: str) -> bytes:
        return self._safe_path(storage_path).read_bytes()

    def exists(self, storage_path: str) -> bool:
        return self._safe_path(storage_path).is_file()

    def delete(self, storage_path: str) -> None:
        self._safe_path(storage_path).unlink(missing_ok=True)

    def _safe_path(self, storage_path: str) -> Path:
        """
        Only allow paths inside the upload folder.
        This stops a bad storage_path such as '../../.env' from reading
        files outside data/uploads.
        """
        path = Path(storage_path).resolve()
        root = self.root.resolve()
        if not path.is_relative_to(root):
            raise ValueError(f"storage_path is outside the upload folder: {storage_path}")
        return path
