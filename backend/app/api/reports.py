# -*- coding: utf-8 -*-
"""
Drop-in reports API module with safe schema alignment for inserts.
If your project already has additional endpoints or logic here,
adapt as needed—but the key parts are:
- explicit setting of owner_id, filters_json, time_mode on insert
- minimal list endpoint that reads the existing table
"""
from __future__ import annotations

import os
import json
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

try:
    # Prefer the project's session dependency if it exists
    from app.db.session import get_session as _get_session  # type: ignore
except Exception:
    _get_session = None

from app.db.report_models import Report  # type: ignore

router = APIRouter(prefix="/api/reports", tags=["reports"])


# Fallback session dependency (uses sqlite file by default) --------------------
async def _fallback_session_dep() -> AsyncSession:
    db_url = os.getenv("DATABASE_URL") or "sqlite+aiosqlite:///backend/app.db"
    engine = create_async_engine(db_url, future=True)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as s:
        yield s


def get_session() -> AsyncSession:
    # FastAPI Depends factory (callable), not actually used directly here.
    return _get_session or _fallback_session_dep  # type: ignore


# Request / Response models ----------------------------------------------------
class RunReportRequest(BaseModel):
    name: str = Field(default="report 1")
    updated_window_days: int = Field(default=180)
    projects: List[str] = Field(default_factory=list)
    labels: List[str] = Field(default_factory=list)
    aggregate_by: str = Field(default="both")
    business_mode: str = Field(default="both")
    max_issues: Optional[int] = Field(default=100)
    jql_like: Optional[str] = None
    business_hours_start: str = Field(default="09:00")
    business_hours_end: str = Field(default="17:00")
    business_days: str = Field(default="Mon,Tue,Wed,Thu,Fri")
    timezone: str = Field(default="America/New_York")


class ReportRow(BaseModel):
    id: int
    created_at: Optional[str]
    name: str
    window_days: int
    business_mode: str
    aggregate_by: str
    csv_path: str


# Endpoints --------------------------------------------------------------------
@router.get("", response_model=List[ReportRow])
async def list_reports(session: AsyncSession = Depends(get_session())):
    res = await session.execute(select(Report).order_by(Report.id.desc()))
    rows = res.scalars().all()
    out: List[ReportRow] = []
    for r in rows:
        out.append(
            ReportRow(
                id=r.id,
                created_at=r.created_at.isoformat() if getattr(r, "created_at", None) else None,
                name=getattr(r, "name", "") or "",
                window_days=int(getattr(r, "window_days", 180) or 180),
                business_mode=getattr(r, "business_mode", "both") or "both",
                aggregate_by=getattr(r, "aggregate_by", "both") or "both",
                csv_path=getattr(r, "csv_path", "") or "",
            )
        )
    return out


@router.post("/run")
async def run_report(req: RunReportRequest, session: AsyncSession = Depends(get_session())):
    # Build params & filters blobs
    params = {
        "name": req.name,
        "updated_window_days": req.updated_window_days,
        "projects": req.projects or [],
        "labels": req.labels or [],
        "aggregate_by": req.aggregate_by or "both",
        "business_mode": req.business_mode or "both",
        "max_issues": req.max_issues,
        "jql_like": req.jql_like,
        "business_hours_start": req.business_hours_start,
        "business_hours_end": req.business_hours_end,
        "business_days": req.business_days,
        "timezone": req.timezone,
    }
    filters = {
        "projects": req.projects or [],
        "labels": req.labels or [],
        "jql_like": req.jql_like,
        "max_issues": req.max_issues if req.max_issues is not None else 100,
        "updated_window_days": req.updated_window_days,
    }

    # owner_id: if your auth layer provides a user, set their id here
    # fall back to 1 so NOT NULL doesn't fail
    owner_id = 1

    r = Report(
        created_at=datetime.utcnow(),
        owner_id=owner_id,
        name=req.name or "report",
        params_json=json.dumps(params),
        filters_json=json.dumps(filters),   # avoid NOT NULL error
        window_days=req.updated_window_days or 180,
        time_mode="updated",                # avoid NOT NULL error
        business_mode=req.business_mode or "both",
        aggregate_by=req.aggregate_by or "both",
        csv_path="",
    )
    session.add(r)
    await session.flush()   # ensure r.id assigned
    await session.commit()

    return {"id": r.id, "status": "queued"}
