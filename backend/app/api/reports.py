
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta, timezone
from pathlib import Path
import csv
import json

from .deps import current_admin
from ..db.database import get_sessionmaker
from ..db.jira_models import JiraIssue, JiraTransition
from ..db.report_models import BaseReport, Report, ReportRow, ReportStatusStat
from ..services.business_time import business_seconds_between
from sqlalchemy import select, delete, func

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
    # Sort transitions by time
    transitions = [t for t in transitions if getattr(t, "when", None) is not None]
    transitions.sort(key=lambda t: t.when)

    if transitions:
        timeline = []
        first = transitions[0]
        first_from = getattr(first, "from_status", None)
        first_to = getattr(first, "to_status", None)

        if issue.created and first.when and first_from:
            timeline.append({"start": issue.created, "end": first.when, "status": first_from})

        # between transitions
        for i in range(len(transitions)-1):
            cur = transitions[i]
            nxt = transitions[i+1]
            cur_to = getattr(cur, "to_status", None)
            if cur.when and nxt.when:
                timeline.append({"start": cur.when, "end": nxt.when, "status": cur_to or ""})

        # tail
        last = transitions[-1]
        tail_end = issue.updated or datetime.now(timezone.utc)
        last_to = getattr(last, "to_status", None)
        if last.when and tail_end and last_to:
            timeline.append({"start": last.when, "end": tail_end, "status": last_to})

        # filter bad segments
        out = []
        for seg in timeline:
            if not seg["status"]:
                continue
            if not (seg["start"] and seg["end"]):
                continue
            if seg["end"] <= seg["start"]:
                continue
            out.append(seg)
        return out

    # no transitions; single bucket with current status if available
    if getattr(issue, "created", None) and getattr(issue, "updated", None) and getattr(issue, "status", None):
        return [{"start": issue.created, "end": issue.updated, "status": issue.status}]
    return []

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
        return FileResponse(path=str(p), filename=p.name, media_type="text/csv")

@router.post("/run")
async def run_report(req: RunReportRequest, _=Depends(current_admin)):
    await _ensure_report_tables()
    Session = get_sessionmaker()

    async with Session() as session:
        # time window
        cutoff = datetime.now(timezone.utc) - timedelta(days=req.updated_window_days or 180)

        # load issues in window
        res_issues = await session.execute(select(JiraIssue).where(JiraIssue.updated >= cutoff))
        issues: list[JiraIssue] = res_issues.scalars().all()

        # filter by projects if given
        if req.projects:
            pset = {p.strip().upper() for p in req.projects if p.strip()}
            issues = [i for i in issues if (getattr(i, "project_key", "") or "").upper() in pset]

        # Determine how to join transitions: by issue_key or issue_id
        join_attr = None
        if hasattr(JiraTransition, "issue_key") and hasattr(JiraIssue, "key"):
            join_attr = "issue_key"
            keys = [i.key for i in issues if getattr(i, "key", None)]
            in_values = list({k for k in keys})
        elif hasattr(JiraTransition, "issue_id") and hasattr(JiraIssue, "issue_id"):
            join_attr = "issue_id"
            ids = [i.issue_id for i in issues if getattr(i, "issue_id", None)]
            in_values = list({x for x in ids})
        else:
            # Fallback: no way to pair, run with no transitions
            in_values = []
            join_attr = None

        transitions_by_key: Dict[Any, List[JiraTransition]] = {}
        if join_attr and in_values:
            # Chunk IN list if very large
            CHUNK = 900
            all_rows: List[JiraTransition] = []
            for start in range(0, len(in_values), CHUNK):
                chunk = in_values[start:start+CHUNK]
                col = getattr(JiraTransition, join_attr)
                res_tr = await session.execute(select(JiraTransition).where(col.in_(chunk)))
                all_rows.extend(res_tr.scalars().all())
            # group
            for tr in all_rows:
                k = getattr(tr, join_attr)
                transitions_by_key.setdefault(k, []).append(tr)

        # Create report row
        r = Report(
            name=req.name or f"Report {datetime.utcnow().isoformat(timespec='seconds')}",
            params_json=json.dumps(req.model_dump()),
            window_days=req.updated_window_days or 180,
            business_mode=req.business_mode or "both",
            aggregate_by=req.aggregate_by or "name",
            csv_path="",
        )
        session.add(r)
        await session.flush()  # generate r.id

        # business config
        tz = req.timezone or "America/New_York"
        bh_start = (req.business_hours_start or "09:00")
        bh_end = (req.business_hours_end or "17:00")
        bdays = (req.business_days or "Mon,Tue,Wed,Thu,Fri")

        # iterate issues and compute stats
        for issue in issues:
            row = ReportRow(
                report_id=r.id,
                issue_id=getattr(issue, "issue_id", "") or "",
                issue_key=getattr(issue, "key", "") or "",
                project_key=getattr(issue, "project_key", "") or "",
                issue_type=getattr(issue, "issue_type", "") or "",
                summary=getattr(issue, "summary", "") or "",
                status=getattr(issue, "status", "") or "",
                assignee=getattr(issue, "assignee", "") or "",
                parent_key=getattr(issue, "parent_key", "") or "",
                epic_key=getattr(issue, "epic_key", "") or "",
                created=getattr(issue, "created", None),
                updated=getattr(issue, "updated", None),
            )
            session.add(row)

            # Pull transitions for this issue
            key_val = getattr(issue, "key", None) if join_attr == "issue_key" else getattr(issue, "issue_id", None)
            transitions = transitions_by_key.get(key_val, []) if key_val is not None else []

            timeline = _build_timeline(issue, transitions)
            if not timeline:
                continue

            stats = _summarize(timeline, tz=tz, bh_start=bh_start, bh_end=bh_end, bdays=bdays)
            for status_name, vals in stats.items():
                st = ReportStatusStat(
                    report_id=r.id,
                    issue_key=getattr(issue, "key", "") or "",
                    bucket="name",
                    status=status_name,
                    entered_count=vals["entered_count"],
                    wall_seconds=vals["wall_seconds"],
                    business_seconds=vals["business_seconds"],
                )
                session.add(st)

        await session.commit()

        # Build CSV
        out_dir = _ensure_dirs()
        csv_path = out_dir / f"report_{r.id}.csv"

        res_stats = await session.execute(select(ReportStatusStat).where(ReportStatusStat.report_id == r.id))
        stats_rows = res_stats.scalars().all()

        # Build quick lookup for issue metadata
        meta = {getattr(i, "key", ""): i for i in issues}

        with open(csv_path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["issue_key","project_key","issue_type","assignee","parent_key","epic_key","bucket","status","entered_count","wall_hours","business_hours"])
            for st in stats_rows:
                ii = meta.get(st.issue_key)
                if not ii:
                    continue
                w.writerow([
                    getattr(ii, "key", ""),
                    getattr(ii, "project_key", "") or "",
                    getattr(ii, "issue_type", "") or "",
                    getattr(ii, "assignee", "") or "",
                    getattr(ii, "parent_key", "") or "",
                    getattr(ii, "epic_key", "") or "",
                    st.bucket,
                    st.status,
                    st.entered_count,
                    round(st.wall_seconds/3600.0,3),
                    round(st.business_seconds/3600.0,3)
                ])

        # Save path to DB
        r.csv_path = str(csv_path)
        session.add(r)
        await session.commit()

        return {"ok": True, "report_id": r.id, "csv_path": r.csv_path, "issues_count": len(issues)}
