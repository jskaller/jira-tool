from __future__ import annotations

from sqlalchemy import Column, Integer, Text, DateTime, ForeignKey, func, text
from sqlalchemy.orm import relationship

from app.db.base import Base  # type: ignore

class Report(Base):  # type: ignore[misc]
    __tablename__ = "reports"
    # Avoid "Table 'reports' is already defined" if imported twice by dev server
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    # Keep this present because API may pass owner_id; default to 1 if not supplied.
    owner_id = Column(Integer, nullable=False, default=1, server_default=text("1"))

    # Keep old columns for backward compat, give robust defaults to survive NOT NULL constraints.
    name = Column(Text, nullable=False, default="", server_default=text("''"))
    params_json = Column(Text, nullable=False, default="{}", server_default=text("'{}'"))

    # Newer fields seen in your logs; default them both on client and server side.
    filters_json = Column(Text, nullable=False, default="{}", server_default=text("'{}'"))
    time_mode = Column(Text, nullable=False, default="updated", server_default=text("'updated'"))

    window_days = Column(Integer, nullable=False, default=180, server_default=text("180"))
    business_mode = Column(Text, nullable=False, default="both", server_default=text("'both'"))
    aggregate_by = Column(Text, nullable=False, default="both", server_default=text("'both'"))
    csv_path = Column(Text, nullable=False, default="", server_default=text("''"))
