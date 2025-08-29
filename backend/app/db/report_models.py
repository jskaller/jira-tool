# -*- coding: utf-8 -*-
"""
Drop-in replacement for Report ORM model.
Adds/ensures the following columns exist on the model:
- owner_id (INT, NOT NULL)
- name (TEXT, NOT NULL, default "")
- params_json (TEXT, NOT NULL, default "{}")
- filters_json (TEXT, NOT NULL, default "{}")
- window_days (INT, NOT NULL, default 180)
- time_mode (TEXT, NOT NULL, default "updated")
- business_mode (TEXT, NOT NULL, default "both")
- aggregate_by (TEXT, NOT NULL, default "both")
- csv_path (TEXT, NOT NULL, default "")
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Column, Integer, String, DateTime, Text

# Try to reuse project's Base if present; otherwise fall back to local declarative_base.
Base = None
try:
    # common locations for project's shared Base
    from .base import Base  # type: ignore
except Exception:
    try:
        from .session import Base  # type: ignore
    except Exception:
        try:
            from .models import Base  # type: ignore
        except Exception:
            from sqlalchemy.orm import declarative_base
            Base = declarative_base()  # type: ignore


class Report(Base):  # type: ignore[name-defined]
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Required columns (match DB)
    owner_id = Column(Integer, nullable=False)                                 # user id owning the report
    name = Column(String(255), nullable=False, default="", server_default="")
    params_json = Column(Text, nullable=False, default="{}", server_default="{}")
    filters_json = Column(Text, nullable=False, default="{}", server_default="{}")
    window_days = Column(Integer, nullable=False, default=180, server_default="180")
    time_mode = Column(String(32), nullable=False, default="updated", server_default="updated")  # created|updated
    business_mode = Column(String(32), nullable=False, default="both", server_default="both")    # wall|work|both
    aggregate_by = Column(String(32), nullable=False, default="both", server_default="both")     # created|updated|both
    csv_path = Column(String(512), nullable=False, default="", server_default="")

    # Optional: string repr for debugging
    def __repr__(self) -> str:  # pragma: no cover
        return f"<Report id={self.id} name={self.name!r} owner_id={self.owner_id}>"
