"""
All database models live here so that `init_db()` can create every table.

When you add a model, import it below as well.
"""
from app.shared.models.base import Base
from app.shared.models.file import File, ProcessingStatus, new_file_id
from app.shared.models.document_content import DocumentContent
from app.shared.models.document_chunk import DocumentChunk

__all__ = [
    "Base", "File", "ProcessingStatus", "new_file_id",
    "DocumentContent", "DocumentChunk",
]
