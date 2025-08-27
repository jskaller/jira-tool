from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, DateTime, ForeignKey, Text, JSON, UniqueConstraint
from datetime import datetime, timezone
from .database import Base

def now_utc():
    return datetime.now(timezone.utc)

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(String(20), default="admin")  # 'admin' or 'user'
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

class Settings(Base):
    __tablename__ = "settings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    jira_base_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    jira_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    jira_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    default_window_days: Mapped[int] = mapped_column(Integer, default=180)
    business_hours_start: Mapped[str] = mapped_column(String(5), default="09:00")
    business_hours_end: Mapped[str] = mapped_column(String(5), default="17:00")
    business_days: Mapped[str] = mapped_column(String(50), default="Mon,Tue,Wed,Thu,Fri")
    timezone: Mapped[str] = mapped_column(String(64), default="America/New_York")

class Report(Base):
    __tablename__ = "reports"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, index=True)
    filters_json: Mapped[dict] = mapped_column(JSON, default={})
    time_mode: Mapped[str] = mapped_column(String(16), default="business_hours")
    window_days: Mapped[int] = mapped_column(Integer, default=180)
    projects_json: Mapped[list] = mapped_column(JSON, default=[])
    jql: Mapped[str | None] = mapped_column(Text, nullable=True)
    status_group_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    state: Mapped[str] = mapped_column(String(16), default="complete")  # 'pending'|'running'|'complete'|'failed'
    title: Mapped[str] = mapped_column(String(255), default="Sample Report")

class Issue(Base):
    __tablename__ = "issues"
    __table_args__ = (UniqueConstraint("report_id", "issue_key", name="uq_issue_report_key"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    report_id: Mapped[int] = mapped_column(Integer, ForeignKey("reports.id"), index=True)
    issue_key: Mapped[str] = mapped_column(String(32), index=True)
    project_key: Mapped[str] = mapped_column(String(32))
    type: Mapped[str] = mapped_column(String(50))
    summary: Mapped[str] = mapped_column(Text)
    epic_key: Mapped[str | None] = mapped_column(String(32), nullable=True)
    parent_key: Mapped[str | None] = mapped_column(String(32), nullable=True)
    labels_json: Mapped[list] = mapped_column(JSON, default=[])
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    current_status: Mapped[str] = mapped_column(String(50), default="To Do")
    assignee: Mapped[str | None] = mapped_column(String(255), nullable=True)

class Transition(Base):
    __tablename__ = "transitions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    report_id: Mapped[int] = mapped_column(Integer, ForeignKey("reports.id"), index=True)
    issue_key: Mapped[str] = mapped_column(String(32), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    from_status: Mapped[str] = mapped_column(String(50))
    to_status: Mapped[str] = mapped_column(String(50))
    transitioned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    actor: Mapped[str | None] = mapped_column(String(255), nullable=True)

class MetricIssue(Base):
    __tablename__ = "metrics_issue"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    report_id: Mapped[int] = mapped_column(Integer, index=True)
    issue_key: Mapped[str] = mapped_column(String(32), index=True)
    bucket: Mapped[str] = mapped_column(String(64))  # status name or category
    time_seconds: Mapped[int] = mapped_column(Integer, default=0)
    entries_count: Mapped[int] = mapped_column(Integer, default=0)

class MetricRollup(Base):
    __tablename__ = "metrics_rollup"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    report_id: Mapped[int] = mapped_column(Integer, index=True)
    node_type: Mapped[str] = mapped_column(String(16))  # 'epic'|'parent'
    node_key: Mapped[str] = mapped_column(String(32))
    bucket: Mapped[str] = mapped_column(String(64))
    time_seconds_sum: Mapped[int] = mapped_column(Integer, default=0)
    entries_count_sum: Mapped[int] = mapped_column(Integer, default=0)
