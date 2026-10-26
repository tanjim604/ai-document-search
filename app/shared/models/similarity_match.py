
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models.base import Base


class SimilarityMatch(Base):
    """Record an exact duplicate or semantic match between two files."""

    __tablename__ = "similarity_matches"

    __table_args__ = (
        UniqueConstraint(
            "source_file_id",
            "matched_file_id",
            "match_type",
            name="uq_similarity_match_pair_type",
        ),
        CheckConstraint(
            "similarity_score >= 0 AND similarity_score <= 1",
            name="ck_similarity_score_range",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    source_file_id: Mapped[str] = mapped_column(
        String(40),
        ForeignKey("files.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    matched_file_id: Mapped[str] = mapped_column(
        String(40),
        ForeignKey("files.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    similarity_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    # exact_duplicate, near_duplicate, or related
    match_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
