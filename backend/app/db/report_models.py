
from __future__ import annotations
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import Integer, String, DateTime, ForeignKey, Text
from datetime import datetime

class BaseReport(DeclarativeBase):
    pass

class Report(BaseReport):
    __tablename__ = "reports"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    name: Mapped[str] = mapped_column(String(255), default="Report")
    params_json: Mapped[str] = mapped_column(Text, default="{}")
    # convenience columns
    window_days: Mapped[int] = mapped_column(Integer, default=180)
    business_mode: Mapped[str] = mapped_column(String(16), default="business")  # business|wall|both
    aggregate_by: Mapped[str] = mapped_column(String(16), default="name")       # name|both (category later)
    csv_path: Mapped[str] = mapped_column(String(1024), default="")

    rows: Mapped[list["ReportRow"]] = relationship(back_populates="report", cascade="all, delete-orphan")
    stats: Mapped[list["ReportStatusStat"]] = relationship(back_populates="report", cascade="all, delete-orphan")

class ReportRow(BaseReport):
    __tablename__ = "report_rows"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("reports.id", ondelete="CASCADE"))
    issue_id: Mapped[str] = mapped_column(String(50))
    issue_key: Mapped[str] = mapped_column(String(50))
    project_key: Mapped[str] = mapped_column(String(50))
    issue_type: Mapped[str] = mapped_column(String(50))
    summary: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(100))
    assignee: Mapped[str] = mapped_column(String(255))
    parent_key: Mapped[str] = mapped_column(String(50))
    epic_key: Mapped[str] = mapped_column(String(50))
    created: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    report: Mapped["Report"] = relationship(back_populates="rows")

class ReportStatusStat(BaseReport):
    __tablename__ = "report_status_stats"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("reports.id", ondelete="CASCADE"))
    issue_key: Mapped[str] = mapped_column(String(50))
    bucket: Mapped[str] = mapped_column(String(32), default="name")  # name|category (category later)
    status: Mapped[str] = mapped_column(String(100))

    entered_count: Mapped[int] = mapped_column(Integer, default=0)
    wall_seconds: Mapped[int] = mapped_column(Integer, default=0)
    business_seconds: Mapped[int] = mapped_column(Integer, default=0)

    report: Mapped["Report"] = relationship(back_populates="stats")
