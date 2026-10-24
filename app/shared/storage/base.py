"""
Storage interface.

Every storage adapter (local disk now, cloud later) must provide these four
methods. The rest of the system only talks to this interface, so switching
from local disk to S3 / Azure Blob / Google Cloud Storage later means writing
one new class, not changing Diya's, Zahid's or Tanjim's code.
"""
from abc import ABC, abstractmethod


class StorageBackend(ABC):
    @abstractmethod
    def save(self, file_id: str, extension: str, data: bytes) -> str:
        """Save the bytes and return the storage_path to put in the database."""

    @abstractmethod
    def read_bytes(self, storage_path: str) -> bytes:
        """Return the original file's bytes."""

    @abstractmethod
    def exists(self, storage_path: str) -> bool:
        """True if something is stored at storage_path."""

    @abstractmethod
    def delete(self, storage_path: str) -> None:
        """Remove the stored file. Does nothing if it is already gone."""
