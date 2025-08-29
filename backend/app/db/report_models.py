
from __future__ import annotations
from datetime import datetime
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, String, Text, DateTime

BaseReport = declarative_base()

class Report(BaseReport):
    __tablename__ = "reports"
    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    # Owner of the report (user id). Existing DBs already have NOT NULL constraint.
    owner_id = Column(Integer, nullable=False)
    # Metadata
    name = Column(String(255), default="Report", nullable=False)
    params_json = Column(Text, default="{}", nullable=False)
    window_days = Column(Integer, default=180, nullable=False)
    business_mode = Column(String(20), default="both", nullable=False)   # business|wall|both
    aggregate_by = Column(String(20), default="name", nullable=False)     # name|both (category later)
    csv_path = Column(Text, default="", nullable=False)

class ReportRow(BaseReport):
    __tablename__ = "report_rows"
    id = Column(Integer, primary_key=True, autoincrement=True)
    report_id = Column(Integer, nullable=False)
    issue_id = Column(String(64))
    issue_key = Column(String(64))
    project_key = Column(String(64))
    issue_type = Column(String(64))
    summary = Column(Text)
    status = Column(String(128))
    assignee = Column(String(128))
    parent_key = Column(String(64))
    epic_key = Column(String(64))
    created = Column(DateTime, nullable=True)
    updated = Column(DateTime, nullable=True)

class ReportStatusStat(BaseReport):
    __tablename__ = "report_status_stats"
    id = Column(Integer, primary_key=True, autoincrement=True)
    report_id = Column(Integer, nullable=False)
    issue_key = Column(String(64), nullable=False)
    bucket = Column(String(20), default="name", nullable=False) # name|category
    status = Column(String(128), nullable=False)
    entered_count = Column(Integer, default=0, nullable=False)
    wall_seconds = Column(Integer, default=0, nullable=False)
    business_seconds = Column(Integer, default=0, nullable=False)
