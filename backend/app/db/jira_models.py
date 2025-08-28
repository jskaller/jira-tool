from sqlalchemy.orm import declarative_base, Mapped, mapped_column
from sqlalchemy import Integer, String, Text, DateTime, Index

BaseJira = declarative_base()

class JiraIssue(BaseJira):
    __tablename__ = "jira_issues"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    issue_id: Mapped[str] = mapped_column(String(50), unique=True, index=True)  # Jira numeric id as string
    key: Mapped[str] = mapped_column(String(32), index=True)
    project_key: Mapped[str] = mapped_column(String(32), index=True)
    issue_type: Mapped[str] = mapped_column(String(64), default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(64), default="")
    assignee: Mapped[str] = mapped_column(String(255), default="")
    epic_key: Mapped[str] = mapped_column(String(32), default="")
    parent_key: Mapped[str] = mapped_column(String(32), default="")
    created: Mapped[DateTime] = mapped_column(DateTime, nullable=True)
    updated: Mapped[DateTime] = mapped_column(DateTime, nullable=True)
    raw_json: Mapped[str] = mapped_column(Text, default="")  # raw issue payload as JSON string

Index("idx_jira_issues_project_updated", JiraIssue.project_key, JiraIssue.updated)

class JiraTransition(BaseJira):
    __tablename__ = "jira_transitions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    issue_id: Mapped[str] = mapped_column(String(50), index=True)  # Jira numeric id (string) for join
    issue_key: Mapped[str] = mapped_column(String(32), index=True)
    when: Mapped[DateTime] = mapped_column(DateTime, index=True)
    author: Mapped[str] = mapped_column(String(255), default="")
    from_status: Mapped[str] = mapped_column(String(64), default="")
    to_status: Mapped[str] = mapped_column(String(64), default="")
