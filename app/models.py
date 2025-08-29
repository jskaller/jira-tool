from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Integer, Text
from .db import Base

class ReportRun(Base):
    __tablename__ = "report_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    started_at: Mapped[str] = mapped_column(String(32))
    completed_at: Mapped[str] = mapped_column(String(32), nullable=True)
    created_by: Mapped[str] = mapped_column(String(255))
    projects: Mapped[str] = mapped_column(Text)
    jql: Mapped[str] = mapped_column(Text)
    time_mode: Mapped[str] = mapped_column(String(16))   # business|24x7
    timezone: Mapped[str] = mapped_column(String(64))
    agg_mode: Mapped[str] = mapped_column(String(16))    # name|category|both|custom
    custom_buckets: Mapped[str] = mapped_column(Text, nullable=True)
    epic_rollup: Mapped[str] = mapped_column(String(16)) # full_rollup|epic_only
    status: Mapped[str] = mapped_column(String(16))      # running|ok|error
    error: Mapped[str] = mapped_column(Text, nullable=True)
    csv_issues_path: Mapped[str] = mapped_column(Text, nullable=True)
    csv_transitions_path: Mapped[str] = mapped_column(Text, nullable=True)
    meta: Mapped[str] = mapped_column(Text, nullable=True)

class SettingsRow(Base):
    __tablename__ = "settings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)  # always 1
    jira_base_url: Mapped[str] = mapped_column(Text, default="")
    jira_email: Mapped[str] = mapped_column(Text, default="")
    jira_api_token_cipher: Mapped[str] = mapped_column(Text, default="")  # encrypted
    default_window_days: Mapped[int] = mapped_column(Integer, default=180)
    business_hours_start: Mapped[str] = mapped_column(String(8), default="09:00")
    business_hours_end: Mapped[str] = mapped_column(String(8), default="17:00")
    business_days: Mapped[str] = mapped_column(String(64), default="Mon,Tue,Wed,Thu,Fri")
    timezone: Mapped[str] = mapped_column(String(64), default="America/New_York")
