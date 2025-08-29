from pydantic import BaseModel, Field
from typing import List, Literal, Optional, Dict, Any

class RunRequest(BaseModel):
    report: Literal["status_summary","throughput","cycle_time","aging_wip"] = "status_summary"
    project_keys: List[str] = Field(..., min_items=1)
    aggregation: Literal["status","category","both","custom"] = "both"
    custom_buckets: Optional[Dict[str,str]] = None
    business_hours: bool = True
    timezone: str = "America/New_York"
    epic_rollup: Literal["epic_only","full_rollup"] = "full_rollup"
    jql: Optional[str] = None
    window_days: Optional[int] = None
    labels: Optional[List[str]] = None
    epics: Optional[List[str]] = None
    max_issues: Optional[int] = 25  # NEW: test-time cap

class RunResponse(BaseModel):
    run_id: int
    status: str
    csv_issues_url: Optional[str] = None
    csv_transitions_url: Optional[str] = None
    meta: Dict[str, Any] = {}
