
from sqlalchemy import String, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models.base import Base


class DocumentContent(Base):
    __tablename__ = "document_contents"

    file_id: Mapped[str] = mapped_column(
        String(40),
        ForeignKey("files.id"),
        primary_key=True
    )

    raw_text: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )

    summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )
