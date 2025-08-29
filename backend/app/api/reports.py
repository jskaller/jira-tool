from __future__ import annotations

import json
from typing import List, Optional, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_session
from app.db.report_models import Report

router = APIRouter(prefix="/api/reports", tags=["reports"])

class ReportRunRequest(BaseModel):
    name: str = Field(default="report")
    projects: List[str] = Field(default_factory=list)
    labels: List[str] = Field(default_factory=list)
    updated_window_days: int = 180
    business_mode: Literal["wall", "work", "both"] = "both"
    aggregate_by: Literal["assignee", "status", "both"] = "both"
    time_mode: Literal["business", "wall", "both"] = "both"
    max_issues: int = 100
    jql_like: Optional[str] = None
    business_hours_start: str = "09:00"
    business_hours_end: str = "17:00"
    business_days: str = "Mon,Tue,Wed,Thu,Fri"
    timezone: str = "America/New_York"


@router.get("", summary="List reports")
@router.get("/", summary="List reports (slash)")
async def list_reports(session: AsyncSession = Depends(get_session)):
    res = await session.execute(select(Report).order_by(Report.id.desc()))
    items = res.scalars().all()
    return [
        {
            "id": r.id,
            "name": r.name,
            "created_at": r.created_at,
            "window_days": r.window_days,
            "business_mode": r.business_mode,
            "aggregate_by": r.aggregate_by,
            "time_mode": r.time_mode,
            "csv_path": r.csv_path,
        }
        for r in items
    ]


@router.post("/run", summary="Create and record a report run")
async def run_report(payload: ReportRunRequest, session: AsyncSession = Depends(get_session)):
    # Partition inputs into params vs filters (handy for querying later)
    filters = {
        "projects": payload.projects,
        "labels": payload.labels,
        "jql_like": payload.jql_like,
        "max_issues": payload.max_issues,
        "updated_window_days": payload.updated_window_days,
    }
    params = payload.model_dump()

    r = Report(
        name=payload.name,
        params_json=json.dumps(params, ensure_ascii=False),
        filters_json=json.dumps(filters, ensure_ascii=False),
        window_days=payload.updated_window_days,
        business_mode=payload.business_mode,
        aggregate_by=payload.aggregate_by,
        time_mode=payload.time_mode,
        # owner_id could be derived from auth; keep None for now
        owner_id=None,
        csv_path="",  # will be populated by the job that generates CSVs
    )
    session.add(r)
    await session.flush()
    await session.commit()
    return {"ok": True, "report_id": r.id}
