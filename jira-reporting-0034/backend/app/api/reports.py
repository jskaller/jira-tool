
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
from sqlalchemy import select, delete, text

router = APIRouter(prefix="/reports", tags=["reports"])

class RunReportRequest(BaseModel):
    name: Optional[str] = None
    updated_window_days: int = 180
    projects: List[str] = Field(default_factory=list)
    labels: List[str] = Field(default_factory=list)  # reserved
    aggregate_by: str = "name"   # name|both (category later)
    business_mode: str = "both"  # business|wall|both
    max_issues: int = 25000
    jql_like: Optional[str] = None  # reserved, local filter
    business_hours_start: Optional[str] = None
    business_hours_end: Optional[str] = None
    business_days: Optional[str] = None
    timezone: Optional[str] = None

def _ensure_dirs() -> Path:
    p = Path("storage/reports")
    p.mkdir(parents=True, exist_ok=True)
    return p

async def _ensure_report_tables():
    """Create tables if missing and migrate columns if older schema exists."""
    Session = get_sessionmaker()
    async with Session() as session:
        def _create(sync_session):
            bind = sync_session.get_bind()
            BaseReport.metadata.create_all(bind=bind)
        await session.run_sync(_create)

        # Minimal migrations for SQLite (add missing columns to 'reports')
        cols = {row['name'] for row in (await session.execute(text("PRAGMA table_info(reports)"))).mappings()}
        needed = {
            'name': "TEXT DEFAULT 'Report'",
            'params_json': "TEXT DEFAULT '{}'",
            'window_days': "INTEGER DEFAULT 180",
            'business_mode': "TEXT DEFAULT 'both'",
            'aggregate_by': "TEXT DEFAULT 'name'",
            'csv_path': "TEXT DEFAULT ''",
        }
        for col, ddl in needed.items():
            if col not in cols:
                await session.execute(text(f"ALTER TABLE reports ADD COLUMN {col} {ddl}"))
        await session.commit()

def _in_project(pkeys: List[str], project_key: str) -> bool:
    if not pkeys:
        return True
    pkeys_norm = [x.strip().upper() for x in pkeys if x.strip()]
    return (project_key or "").upper() in pkeys_norm

def _build_timeline(issue: JiraIssue, transitions: List[JiraTransition]) -> List[Dict[str, Any]]:
    transitions = [t for t in transitions if getattr(t, "when", None) is not None]
    transitions.sort(key=lambda t: t.when)

    if transitions:
        timeline = []
        first = transitions[0]
        first_from = getattr(first, "from_status", None)

        if issue.created and first.when and first_from:
            timeline.append({"start": issue.created, "end": first.when, "status": first_from})

        for i in range(len(transitions)-1):
            cur = transitions[i]; nxt = transitions[i+1]
            cur_to = getattr(cur, "to_status", None)
            if cur.when and nxt.when:
                timeline.append({"start": cur.when, "end": nxt.when, "status": cur_to or ""})

        last = transitions[-1]
        tail_end = issue.updated or datetime.now(timezone.utc)
        last_to = getattr(last, "to_status", None)
        if last.when and tail_end and last_to:
            timeline.append({"start": last.when, "end": tail_end, "status": last_to})

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

    if getattr(issue, "created", None) and getattr(issue, "updated", None) and getattr(issue, "status", None):
        return [{"start": issue.created, "end": issue.updated, "status": issue.status}]
    return []

def _summarize(tl: List[Dict[str, Any]], tz: str, bs: str, be: str, bdays: str) -> Dict[str, Dict[str, Any]]:
    agg: Dict[str, Dict[str, Any]] = {}
    for seg in tl:
        st = seg["status"]
        wall = int((seg["end"] - seg["start"]).total_seconds())
        biz = business_seconds_between(seg["start"], seg["end"], tz_name=tz, business_start=bs, business_end=be, business_days_csv=bdays)
        bucket = agg.setdefault(st, {"entered_count": 0, "wall_seconds": 0, "business_seconds": 0})
        bucket["entered_count"] += 1; bucket["wall_seconds"] += wall; bucket["business_seconds"] += biz
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
        await session.execute(text("DELETE FROM report_status_stats WHERE report_id = :rid"), {"rid": report_id})
        await session.execute(text("DELETE FROM report_rows WHERE report_id = :rid"), {"rid": report_id})
        await session.execute(text("DELETE FROM reports WHERE id = :rid"), {"rid": report_id})
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
        cutoff = datetime.now(timezone.utc) - timedelta(days=req.updated_window_days or 180)

        # Load issues in window (limit + order)
        stmt = select(JiraIssue).where(JiraIssue.updated >= cutoff).order_by(JiraIssue.updated.desc()).limit(req.max_issues or 25000)
        res_issues = await session.execute(stmt)
        issues: list[JiraIssue] = res_issues.scalars().all()

        if req.projects:
            pset = {p.strip().upper() for p in req.projects if p.strip()}
            issues = [i for i in issues if (getattr(i, "project_key", "") or "").upper() in pset]

        # Group transitions by issue_key or issue_id
        join_attr = None
        if hasattr(JiraTransition, "issue_key") and hasattr(JiraIssue, "key"):
            join_attr = "issue_key"
            in_values = list({i.key for i in issues if getattr(i, "key", None)})
        elif hasattr(JiraTransition, "issue_id") and hasattr(JiraIssue, "issue_id"):
            join_attr = "issue_id"
            in_values = list({i.issue_id for i in issues if getattr(i, "issue_id", None)})
        else:
            in_values = []; join_attr = None

        transitions_by: Dict[str, List[JiraTransition]] = {}
        if join_attr and in_values:
            CHUNK = 900
            col = getattr(JiraTransition, join_attr)
            all_rows: List[JiraTransition] = []
            for s in range(0, len(in_values), CHUNK):
                chunk = in_values[s:s+CHUNK]
                res_tr = await session.execute(select(JiraTransition).where(col.in_(chunk)))
                all_rows.extend(res_tr.scalars().all())
            for tr in all_rows:
                k = getattr(tr, join_attr)
                transitions_by.setdefault(k, []).append(tr)

        # Create report shell
        r = Report(
            name=req.name or f"Report {datetime.utcnow().isoformat(timespec='seconds')}",
            params_json=json.dumps(req.model_dump()),
            window_days=req.updated_window_days or 180,
            business_mode=req.business_mode or "both",
            aggregate_by=req.aggregate_by or "name",
            csv_path="",
        )
        session.add(r); await session.flush()

        tz = req.timezone or "America/New_York"
        bs = (req.business_hours_start or "09:00"); be = (req.business_hours_end or "17:00")
        bdays = (req.business_days or "Mon,Tue,Wed,Thu,Fri")

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

            key_val = getattr(issue, "key", None) if join_attr == "issue_key" else getattr(issue, "issue_id", None)
            transitions = transitions_by.get(key_val, []) if key_val is not None else []
            tl = _build_timeline(issue, transitions)
            if not tl: continue
            agg = _summarize(tl, tz=tz, bs=bs, be=be, bdays=bdays)
            for status_name, vals in agg.items():
                session.add(ReportStatusStat(
                    report_id=r.id,
                    issue_key=getattr(issue, "key", "") or "",
                    bucket="name",
                    status=status_name,
                    entered_count=vals["entered_count"],
                    wall_seconds=vals["wall_seconds"],
                    business_seconds=vals["business_seconds"],
                ))

        await session.commit()

        # CSV
        out_dir = _ensure_dirs(); csv_path = out_dir / f"report_{r.id}.csv"
        res_stats = await session.execute(select(ReportStatusStat).where(ReportStatusStat.report_id == r.id))
        stats_rows = res_stats.scalars().all()
        meta = {getattr(i, "key", ""): i for i in issues}

        with open(csv_path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["issue_key","project_key","issue_type","assignee","parent_key","epic_key","bucket","status","entered_count","wall_hours","business_hours"])
            for st in stats_rows:
                ii = meta.get(st.issue_key)
                if not ii: continue
                w.writerow([
                    getattr(ii, "key", ""),
                    getattr(ii, "project_key", "") or "",
                    getattr(ii, "issue_type", "") or "",
                    getattr(ii, "assignee", "") or "",
                    getattr(ii, "parent_key", "") or "",
                    getattr(ii, "epic_key", "") or "",
                    st.bucket, st.status, st.entered_count,
                    round(st.wall_seconds/3600.0,3), round(st.business_seconds/3600.0,3)
                ])

        r.csv_path = str(csv_path); session.add(r); await session.commit()
        return {"ok": True, "report_id": r.id, "csv_path": r.csv_path, "issues_count": len(issues)}
