# app/db/report_models.py
# Single authoritative SQLAlchemy model for the 'reports' table.
# - Adds missing columns used by API: owner_id, filters_json, time_mode.
# - Provides sane NOT NULL defaults to prevent sqlite IntegrityError.
# - Uses extend_existing=True to avoid 'Table reports is already defined' crashes
#   when another legacy model also declared the same table.

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, func
from sqlalchemy.orm import declarative_base

# IMPORTANT:
# We declare our own Base here to avoid cross-import cycles and to prevent
# duplicate MetaData conflicts in case an older models module declared 'reports' too.
# This keeps the mapper independent and safe to import anywhere.
Base = declarative_base()

class Report(Base):  # type: ignore[misc]
    __tablename__ = "reports"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, server_default=func.now())

    # Required for ownership and filtering by user. Default 0 so NOT NULL inserts never fail
    # even if older code paths forgot to pass it.
    owner_id = Column(Integer, nullable=False, default=0)

    # A human-friendly name for the saved/run report
    name = Column(String(255), nullable=False, default="untitled")

    # JSON blobs stored as TEXT in sqlite
    params_json = Column(Text, nullable=False, default="{}")
    filters_json = Column(Text, nullable=False, default="{}")

    # Window and aggregation controls
    window_days = Column(Integer, nullable=False, default=180)
    business_mode = Column(String(16), nullable=False, default="both")   # "wall" | "business" | "both"
    aggregate_by = Column(String(16), nullable=False, default="both")    # "created" | "resolved" | "both"
    time_mode = Column(String(16), nullable=False, default="updated")    # "updated" | "created" | "resolved" | "both"

    # Path to exported CSV (if any)
    csv_path = Column(String(1024), nullable=False, default="")
