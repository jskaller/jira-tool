from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class UserOut(BaseModel):
    id: int
    email: str
    name: Optional[str] = None
    role: str

class LoginIn(BaseModel):
    email: str
    password: str

class SettingsIn(BaseModel):
    jira_base_url: Optional[str] = None
    jira_email: Optional[str] = None
    jira_api_token: Optional[str] = None
    default_window_days: int = 180
    business_hours_start: str = "09:00"
    business_hours_end: str = "17:00"
    business_days: str = "Mon,Tue,Wed,Thu,Fri"
    timezone: str = "America/New_York"

class SettingsOut(BaseModel):
    jira_base_url: Optional[str] = None
    jira_email: Optional[str] = None
    has_token: bool = False
    default_window_days: int = 180
    business_hours_start: str = "09:00"
    business_hours_end: str = "17:00"
    business_days: str = "Mon,Tue,Wed,Thu,Fri"
    timezone: str = "America/New_York"

class ReportCreate(BaseModel):
    title: str = "Sample Report"
    projects: List[str] = []
    jql: Optional[str] = None
    window_days: int = 180
    time_mode: str = "business_hours"  # or '24x7'

class ReportOut(BaseModel):
    id: int
    title: str
    created_at: datetime
    state: str
    time_mode: str
    window_days: int

class IssueRow(BaseModel):
    issue_key: str
    project_key: str
    type: str
    summary: str
    epic_key: Optional[str] = None
    parent_key: Optional[str] = None
    labels: List[str] = []
    current_status: str
    assignee: Optional[str] = None

class ReportDetail(BaseModel):
    report: ReportOut
    issues: List[IssueRow]
    buckets: Dict[str, Dict[str, int]]  # issue_key -> {bucket: seconds}
