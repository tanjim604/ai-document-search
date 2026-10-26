
import uuid

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models.base import Base


def new_chunk_id():
    return f"c_{uuid.uuid4().hex}"


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    __table_args__ = (
        UniqueConstraint(
            "file_id",
            "chunk_index",
            name="uq_document_chunks_file_index"
        ),
    )

    id: Mapped[str] = mapped_column(
        String(40),
        primary_key=True,
        default=new_chunk_id
    )

    file_id: Mapped[str] = mapped_column(
        String(40),
        ForeignKey("files.id"),
        nullable=False,
        index=True
    )

    chunk_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    text: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )
