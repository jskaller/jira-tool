from __future__ import annotations

import json
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.report_models import Report  # type: ignore
try:
    from app.db.session import get_async_session
except Exception:
    from app.db.session import get_async_session  # type: ignore

router = APIRouter(prefix="/api/reports", tags=["reports"])

class RunReportPayload(BaseModel):
    name: Optional[str] = Field(default=None)
    projects: List[str] = Field(default_factory=list)
    labels: List[str] = Field(default_factory=list)
    updated_window_days: int = 180
    aggregate_by: Literal["assignee", "project", "both"] = "both"
    business_mode: Literal["wall", "work", "both"] = "both"
    time_mode: Literal["created", "updated", "both"] = "both"
    jql_like: Optional[str] = None
    business_hours_start: str = "09:00"
    business_hours_end: str = "17:00"
    business_days: str = "Mon,Tue,Wed,Thu,Fri"
    timezone: str = "America/New_York"
    max_issues: int = 100

@router.get("", status_code=status.HTTP_200_OK)
async def list_reports(session: AsyncSession = Depends(get_async_session)):
    res = await session.execute(select(Report).order_by(Report.id.desc()))
    items = res.scalars().all()
    return [
        {
            "id": r.id,
            "created_at": str(r.created_at),
            "name": r.name,
            "window_days": r.window_days,
            "business_mode": r.business_mode,
            "aggregate_by": r.aggregate_by,
            "time_mode": r.time_mode,
            "csv_path": r.csv_path,
        }
        for r in items
    ]

@router.post("/run", status_code=status.HTTP_200_OK)
async def run_report(
    payload: RunReportPayload,
    session: AsyncSession = Depends(get_async_session),
):
    filters = {
        "projects": payload.projects,
        "labels": payload.labels,
        "jql_like": payload.jql_like,
        "max_issues": payload.max_issues,
        "updated_window_days": payload.updated_window_days,
    }
    name = payload.name or "report"
    r = Report(
        owner_id=1,
        name=name,
        params_json=json.dumps(payload.model_dump()),
        filters_json=json.dumps(filters),
        window_days=payload.updated_window_days,
        business_mode=payload.business_mode,
        aggregate_by=payload.aggregate_by,
        time_mode=payload.time_mode,
        csv_path="",
    )
    session.add(r)
    await session.flush()
    return {"ok": True, "id": r.id, "message": "report created"}
