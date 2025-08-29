from __future__ import annotations

import datetime as dt
from sqlalchemy import String, Integer, Text, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base

class Report(Base):  # type: ignore[name-defined]
    __tablename__ = "reports"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    owner_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1", default=1)
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="", server_default="")
    params_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}", server_default="{}")
    filters_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}", server_default="{}")
    window_days: Mapped[int] = mapped_column(Integer, nullable=False, default=180, server_default="180")
    business_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="both", server_default="both")
    aggregate_by: Mapped[str] = mapped_column(String(32), nullable=False, default="both", server_default="both")
    time_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="both", server_default="both")
    csv_path: Mapped[str] = mapped_column(String(500), nullable=False, default="", server_default="")
