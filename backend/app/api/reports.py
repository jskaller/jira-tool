
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Tuple, Iterable
from datetime import datetime, timedelta, timezone
from pathlib import Path
import csv
import json

from .deps import current_admin
from ..db.database import get_sessionmaker
from ..db.jira_models import JiraIssue, JiraTransition, BaseJira
from ..db.report_models import BaseReport, Report, ReportRow, ReportStatusStat
from ..services.business_time import business_seconds_between
from sqlalchemy import select, delete
from sqlalchemy.orm import joinedload

router = APIRouter(prefix="/reports", tags=["reports"])

class RunReportRequest(BaseModel):
    name: Optional[str] = None
    updated_window_days: int = 180
    projects: List[str] = Field(default_factory=list)
    labels: List[str] = Field(default_factory=list)  # reserved
    aggregate_by: str = "name"   # name|both (category later)
    business_mode: str = "both"  # business|wall|both
    jql_like: Optional[str] = None  # reserved, local filter
    # Admin-calculated fields (read from settings)
    business_hours_start: Optional[str] = None
    business_hours_end: Optional[str] = None
    business_days: Optional[str] = None
    timezone: Optional[str] = None

def _ensure_dirs() -> Path:
    p = Path("storage/reports")
    p.mkdir(parents=True, exist_ok=True)
    return p

async def _ensure_report_tables():
    Session = get_sessionmaker()
    async with Session() as session:
        def _create(sync_session):
            bind = sync_session.get_bind()
            BaseReport.metadata.create_all(bind=bind)
        await session.run_sync(_create)

def _in_project(pkeys: List[str], project_key: str) -> bool:
    if not pkeys:
        return True
    pkeys_norm = [x.strip().upper() for x in pkeys if x.strip()]
    return (project_key or "").upper() in pkeys_norm

def _build_timeline(issue: JiraIssue, transitions: List[JiraTransition]) -> List[Dict[str, Any]]:
    """
    Returns list of {start, end, status} datetimes for this issue based on transitions.
    """
    if transitions:
        transitions = sorted(transitions, key=lambda t: t.when)
        timeline = []
        first = transitions[0]
        if issue.created and first.when and first.from_status:
            timeline.append({"start": issue.created, "end": first.when, "status": first.from_status})
        # between transitions
        for i in range(len(transitions)-1):
            cur = transitions[i]
            nxt = transitions[i+1]
            if cur.when and nxt.when:
                timeline.append({"start": cur.when, "end": nxt.when, "status": cur.to_status or ""})
        # tail
        last = transitions[-1]
        tail_end = issue.updated or datetime.now(timezone.utc)
        if last.when and tail_end and last.to_status:
            timeline.append({"start": last.when, "end": tail_end, "status": last.to_status})
        # remove bad segments
        return [seg for seg in timeline if seg["end"] and seg["start"] and seg["end"] > seg["start"] and seg["status"]]
    else:
        # no transitions; single bucket with current status
        if not (issue.created and issue.updated and issue.status):
            return []
        return [{"start": issue.created, "end": issue.updated, "status": issue.status}]

def _summarize(timeline: List[Dict[str, Any]], tz: str, bh_start: str, bh_end: str, bdays: str) -> Dict[str, Dict[str, Any]]:
    agg: Dict[str, Dict[str, Any]] = {}
    for seg in timeline:
        st = seg["status"]
        wall = int((seg["end"] - seg["start"]).total_seconds())
        biz = business_seconds_between(seg["start"], seg["end"], tz_name=tz, business_start=bh_start, business_end=bh_end, business_days_csv=bdays)
        bucket = agg.setdefault(st, {"entered_count": 0, "wall_seconds": 0, "business_seconds": 0})
        bucket["entered_count"] += 1
        bucket["wall_seconds"] += wall
        bucket["business_seconds"] += biz
    return agg

def _hours(sec: int) -> float:
    return round(sec / 3600.0, 3)

@router.get("")
async def list_reports(_=Depends(current_admin)):
    await _ensure_report_tables()
    Session = get_sessionmaker()
    async with Session() as session:
        res = await session.execute(select(Report).order_by(Report.id.desc()))
        rows = res.scalars().all()
        return [{
            "id": r.id,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "name": r.name,
            "window_days": r.window_days,
            "business_mode": r.business_mode,
            "aggregate_by": r.aggregate_by,
            "csv_path": r.csv_path,
        } for r in rows]

@router.delete("/{report_id}")
async def delete_report(report_id: int, _=Depends(current_admin)):
    await _ensure_report_tables()
    Session = get_sessionmaker()
    async with Session() as session:
        await session.execute(delete(ReportStatusStat).where(ReportStatusStat.report_id == report_id))
        await session.execute(delete(ReportRow).where(ReportRow.report_id == report_id))
        await session.execute(delete(Report).where(Report.id == report_id))
        await session.commit()
    return {"ok": True}

@router.get("/{report_id}/csv")
async def download_csv(report_id: int, _=Depends(current_admin)):
    await _ensure_report_tables()
    Session = get_sessionmaker()
    async with Session() as session:
        res = await session.execute(select(Report).where(Report.id==report_id))
        r = res.scalar_one_or_none()
        if not r or not r.csv_path:
            raise HTTPException(status_code=404, detail="Report or CSV not found")
        p = Path(r.csv_path)
        if not p.exists():
            raise HTTPException(status_code=404, detail="CSV file missing on disk")
        # FastAPI will serve from working dir
        return FileResponse(path=str(p), filename=p.name, media_type="text/csv")

@router.post("/run")
async def run_report(req: RunReportRequest, _=Depends(current_admin)):
    await _ensure_report_tables()
    Session = get_sessionmaker()

    # load Jira issues + transitions from local DB
    async with Session() as session:
        cutoff = datetime.now(timezone.utc) - timedelta(days=req.updated_window_days or 180)
        res = await session.execute(
            select(JiraIssue).options(joinedload(JiraIssue.transitions)).where(JiraIssue.updated >= cutoff)
        )
        issues: list[JiraIssue] = res.scalars().unique().all()

        # filter by project keys if provided
        issues = [i for i in issues if _in_project(req.projects, i.project_key or "")]

        # prepare report
        r = Report(
            name=req.name or f"Report {datetime.utcnow().isoformat(timespec='seconds')}",
            params_json=json.dumps(req.model_dump()),
            window_days=req.updated_window_days or 180,
            business_mode=req.business_mode or "both",
            aggregate_by=req.aggregate_by or "name",
            csv_path="",
        )
        session.add(r)
        await session.flush()  # get r.id

        # business config
        tz = req.timezone or "America/New_York"
        bh_start = (req.business_hours_start or "09:00")
        bh_end = (req.business_hours_end or "17:00")
        bdays = (req.business_days or "Mon,Tue,Wed,Thu,Fri")

        # iterate issues
        for issue in issues:
            row = ReportRow(
                report_id=r.id,
                issue_id=issue.issue_id,
                issue_key=issue.key,
                project_key=issue.project_key or "",
                issue_type=issue.issue_type or "",
                summary=issue.summary or "",
                status=issue.status or "",
                assignee=issue.assignee or "",
                parent_key=issue.parent_key or "",
                epic_key=issue.epic_key or "",
                created=issue.created,
                updated=issue.updated,
            )
            session.add(row)

            timeline = _build_timeline(issue, issue.transitions or [])
            if not timeline:
                continue
            stats = _summarize(timeline, tz=tz, bh_start=bh_start, bh_end=bh_end, bdays=bdays)
            for status_name, vals in stats.items():
                st = ReportStatusStat(
                    report_id=r.id,
                    issue_key=issue.key,
                    bucket="name",
                    status=status_name,
                    entered_count=vals["entered_count"],
                    wall_seconds=vals["wall_seconds"],
                    business_seconds=vals["business_seconds"],
                )
                session.add(st)

        await session.commit()

        # Build CSV in storage/reports
        out_dir = _ensure_dirs()
        csv_path = out_dir / f"report_{r.id}.csv"
        # CSV schema v1:
        # issue_key, project_key, issue_type, assignee, parent_key, epic_key, bucket, status, entered_count, wall_hours, business_hours
        # One row per (issue,status)
        res_stats = await session.execute(select(ReportStatusStat).where(ReportStatusStat.report_id == r.id))
        stats = res_stats.scalars().all()

        with open(csv_path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["issue_key","project_key","issue_type","assignee","parent_key","epic_key","bucket","status","entered_count","wall_hours","business_hours"])
            # for resolving metadata per issue:
            meta = {i.issue_key: i for i in issues}
            for st in stats:
                ii = meta.get(st.issue_key)
                if not ii:
                    continue
                w.writerow([
                    ii.key, ii.project_key or "", ii.issue_type or "", ii.assignee or "", ii.parent_key or "", ii.epic_key or "",
                    st.bucket, st.status, st.entered_count, round(st.wall_seconds/3600.0,3), round(st.business_seconds/3600.0,3)
                ])

        # save path
        r.csv_path = str(csv_path)
        session.add(r)
        await session.commit()

        return {"ok": True, "report_id": r.id, "csv_path": r.csv_path, "issues_count": len(issues)}
