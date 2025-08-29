from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Integer, String, Text, DateTime, ForeignKey

# IMPORTANT:
# - This class uses __table_args__ = {'extend_existing': True} so that if any
#   older module already registered a 'reports' Table on this metadata, we
#   extend it instead of crashing with "Table 'reports' is already defined".
# - All NOT NULL columns have default+server_default to protect existing rows.
#
# Your project should expose a shared Base. Adjust this import if your Base lives elsewhere.
try:
    # Most common place in this codebase
    from app.db.database import Base  # type: ignore
except Exception:
    # Fallback to a local declarative base if the above import path differs in your repo.
    from sqlalchemy.orm import DeclarativeBase
    class Base(DeclarativeBase):
        pass

class Report(Base):  # type: ignore[name-defined]
    __tablename__ = "reports"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    # Ownership (nullable to avoid legacy rows failing inserts)
    owner_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )

    # Human-friendly name
    name: Mapped[str] = mapped_column(
        String(255), nullable=False, default="untitled", server_default="untitled"
    )

    # Serialized parameters / filters
    params_json: Mapped[str] = mapped_column(
        Text, nullable=False, default="{}", server_default="{}"
    )
    filters_json: Mapped[str] = mapped_column(
        Text, nullable=False, default="{}", server_default="{}"
    )

    # Report config
    window_days: Mapped[int] = mapped_column(
        Integer, nullable=False, default=90, server_default="90"
    )
    business_mode: Mapped[str] = mapped_column(
        String(20), nullable=False, default="wall", server_default="wall"
    )
    aggregate_by: Mapped[str] = mapped_column(
        String(20), nullable=False, default="both", server_default="both"
    )
    time_mode: Mapped[str] = mapped_column(
        String(20), nullable=False, default="updated", server_default="updated"
    )

    # Output path (if any)
    csv_path: Mapped[str] = mapped_column(
        String(1024), nullable=False, default="", server_default=""
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Report id={self.id} name={self.name!r}>"
