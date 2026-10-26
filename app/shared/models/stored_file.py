"""
The bytes of an uploaded file, when STORAGE_BACKEND=database.

Kept in its own table, apart from `files`, so listing or searching files never
loads file contents. `path` is the same value as File.storage_path.
"""
from datetime import datetime

from sqlalchemy import DateTime, Integer, LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models.base import Base
from app.shared.models.file import utc_now


class StoredFile(Base):
    __tablename__ = "stored_files"

    path: Mapped[str] = mapped_column(String(500), primary_key=True)
    data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
