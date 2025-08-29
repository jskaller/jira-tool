from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Integer, String, Text
from sqlalchemy import text as sa_text
from sqlalchemy.orm import Mapped, mapped_column

# Import the project's shared Base (via shim for safety)
from .base import Base  # type: ignore


class Report(Base):  # type: ignore[misc]
    __tablename__ = "reports"
    # Allow live-reload / multiple imports without metadata conflicts
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # Keep both client- and server-side defaults so inserts never fail.
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=datetime.utcnow,
        server_default=sa_text("(datetime('now'))"),
    )

    # Make owner_id optional on the ORM side to avoid IntegrityError when
    # older DBs don't have a default yet. API can (and often does) pass it.
    owner_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Columns that were missing on older DBs — give them safe defaults
    name: Mapped[str] = mapped_column(
        String(255), nullable=False, default="", server_default=sa_text("''")
    )
    params_json: Mapped[str] = mapped_column(
        Text, nullable=False, default="{}", server_default=sa_text("'{}'")
    )
    filters_json: Mapped[str] = mapped_column(
        Text, nullable=False, default="{}", server_default=sa_text("'{}'")
    )
    window_days: Mapped[int] = mapped_column(
        Integer, nullable=False, default=90, server_default=sa_text("90")
    )
    business_mode: Mapped[str] = mapped_column(
        String(32), nullable=False, default="wall", server_default=sa_text("'wall'")
    )
    aggregate_by: Mapped[str] = mapped_column(
        String(32), nullable=False, default="both", server_default=sa_text("'both'")
    )
    time_mode: Mapped[str] = mapped_column(
        String(32), nullable=False, default="updated", server_default=sa_text("'updated'")
    )
    csv_path: Mapped[str] = mapped_column(
        String(512), nullable=False, default="", server_default=sa_text("''")
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Report id={self.id} name={self.name!r} owner_id={self.owner_id}>"
