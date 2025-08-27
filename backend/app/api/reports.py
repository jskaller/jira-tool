from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from sqlalchemy import select, delete
from ..schemas import ReportCreate, ReportOut, ReportDetail, IssueRow
from ..db.database import get_sessionmaker
from ..db.models import Report, Issue, Transition, MetricIssue, MetricRollup
from .deps import current_user
from ..services.csv_export import stream_csv
from datetime import datetime, timezone

router = APIRouter(prefix="/reports", tags=["reports"])

def _sample_data(now: datetime):
    # Fake issues and metrics for demo purposes
    issues = [
        dict(issue_key="AAA-1", project_key="AAA", type="Story", summary="User can log in", epic_key="AAA-EP1", parent_key=None, labels=["auth"], current_status="Done", assignee="alice"),
        dict(issue_key="AAA-2", project_key="AAA", type="Bug", summary="Fix login error", epic_key="AAA-EP1", parent_key=None, labels=["auth","bug"], current_status="In Review", assignee="bob"),
        dict(issue_key="AAA-3", project_key="AAA", type="Sub-task", summary="Write tests", epic_key="AAA-EP1", parent_key="AAA-1", labels=["qa"], current_status="In Progress", assignee="carol"),
    ]
    transitions = [
        # issue AAA-1
        ("AAA-1", 1, "To Do", "In Progress", now.replace(hour=9)),
        ("AAA-1", 2, "In Progress", "In Review", now.replace(hour=13)),
        ("AAA-1", 3, "In Review", "Done", now.replace(hour=16)),
        # issue AAA-2
        ("AAA-2", 1, "To Do", "In Progress", now.replace(hour=10)),
        ("AAA-2", 2, "In Progress", "In Review", now.replace(hour=15)),
        # issue AAA-3
        ("AAA-3", 1, "To Do", "In Progress", now.replace(hour=11)),
    ]
    # Simple per-issue per-bucket seconds (mock)
    buckets = {
        "AAA-1": {"To Do": 3600, "In Progress": 14400, "In Review": 10800, "Done": 0},
        "AAA-2": {"To Do": 7200, "In Progress": 7200, "In Review": 0},
        "AAA-3": {"To Do": 1800, "In Progress": 10800},
    }
    return issues, transitions, buckets

@router.post("", response_model=ReportOut)
async def create_report(payload: ReportCreate, bt: BackgroundTasks, user=Depends(current_user)):
    Session = get_sessionmaker()
    async with Session() as session:
        r = Report(owner_id=user.id, filters_json={"projects": payload.projects, "jql": payload.jql},
                   time_mode=payload.time_mode, window_days=payload.window_days, state="complete", title=payload.title)
        session.add(r)
        await session.flush()
        # Insert sample data
        now = datetime.now(timezone.utc)
        issues, transitions, buckets = _sample_data(now)
        for ii in issues:
            session.add(Issue(report_id=r.id, **ii))
        seq_id = 1
        for (key, seq, fr, to, at) in transitions:
            session.add(Transition(report_id=r.id, issue_key=key, seq=seq, from_status=fr, to_status=to, transitioned_at=at))
        for ikey, m in buckets.items():
            for bucket, secs in m.items():
                session.add(MetricIssue(report_id=r.id, issue_key=ikey, bucket=bucket, time_seconds=int(secs), entries_count=1))
        await session.commit()
        return ReportOut(id=r.id, title=r.title, created_at=r.created_at, state=r.state, time_mode=r.time_mode, window_days=r.window_days)

@router.get("", response_model=list[ReportOut])
async def list_reports(user=Depends(current_user)):
    Session = get_sessionmaker()
    async with Session() as session:
        res = await session.execute(select(Report).order_by(Report.created_at.desc()))
        rows = res.scalars().all()
        return [ReportOut(id=r.id, title=r.title, created_at=r.created_at, state=r.state, time_mode=r.time_mode, window_days=r.window_days) for r in rows]

@router.get("/{rid}", response_model=ReportDetail)
async def get_report(rid: int, user=Depends(current_user)):
    Session = get_sessionmaker()
    async with Session() as session:
        r = (await session.execute(select(Report).where(Report.id == rid))).scalar_one_or_none()
        if not r:
            raise HTTPException(status_code=404, detail="Report not found")
        iss = (await session.execute(select(Issue).where(Issue.report_id == rid))).scalars().all()
        mis = (await session.execute(select(MetricIssue).where(MetricIssue.report_id == rid))).scalars().all()
        buckets = {}
        for m in mis:
            buckets.setdefault(m.issue_key, {})[m.bucket] = m.time_seconds
        issues = [IssueRow(issue_key=i.issue_key, project_key=i.project_key, type=i.type, summary=i.summary,
                           epic_key=i.epic_key, parent_key=i.parent_key, labels=i.labels_json, current_status=i.current_status, assignee=i.assignee)
                  for i in iss]
        return ReportDetail(report=ReportOut(id=r.id, title=r.title, created_at=r.created_at, state=r.state, time_mode=r.time_mode, window_days=r.window_days),
                            issues=issues, buckets=buckets)

@router.get("/{rid}/csv")
async def csv_export(rid: int, type: str = "issues", user=Depends(current_user)):
    Session = get_sessionmaker()
    async with Session() as session:
        rows: list[dict] = []
        if type == "issues":
            iss = (await session.execute(select(Issue).where(Issue.report_id == rid))).scalars().all()
            mis = (await session.execute(select(MetricIssue).where(MetricIssue.report_id == rid))).scalars().all()
            agg = {}
            for m in mis:
                agg.setdefault(m.issue_key, {})[m.bucket] = m.time_seconds
            for i in iss:
                base = dict(report_id=rid, issue_key=i.issue_key, issue_id=i.id, issue_type=i.type, issue_summary=i.summary,
                            project_key=i.project_key, project_name=i.project_key, epic_key=i.epic_key, parent_key=i.parent_key,
                            labels=';'.join(i.labels_json), current_status=i.current_status, assignee=i.assignee, time_mode="mock")
                for bucket, secs in agg.get(i.issue_key, {}).items():
                    base[f"time_in_{bucket}_seconds"] = secs
                rows.append(base)
            return stream_csv(rows, f"report_{rid}_issues.csv")
        elif type == "transitions":
            trs = (await session.execute(select(Transition).where(Transition.report_id == rid))).scalars().all()
            for t in trs:
                rows.append(dict(report_id=rid, issue_key=t.issue_key, from_status=t.from_status, to_status=t.to_status,
                                 transitioned_at=t.transitioned_at.isoformat(), actor=t.actor or ""))
            return stream_csv(rows, f"report_{rid}_transitions.csv")
        else:
            return stream_csv([], f"report_{rid}_empty.csv")

@router.delete("/{rid}")
async def delete_report(rid: int, user=Depends(current_user)):
    Session = get_sessionmaker()
    async with Session() as session:
        await session.execute(delete(Transition).where(Transition.report_id == rid))
        await session.execute(delete(MetricIssue).where(MetricIssue.report_id == rid))
        await session.execute(delete(MetricRollup).where(MetricRollup.report_id == rid))
        await session.execute(delete(Issue).where(Issue.report_id == rid))
        await session.execute(delete(Report).where(Report.id == rid))
        await session.commit()
    return {"ok": True}
