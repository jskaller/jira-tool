from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import text
import csv, json, pathlib
from collections import defaultdict, Counter

from ..effective import load_effective_settings
from ..db import SessionLocal
from ..schemas import RunRequest, RunResponse
from ..services.jira import JiraClient
from ..utils.business_hours import business_seconds_between
from ..utils.jira_times import parse_jira_ts

router = APIRouter(prefix="/api/reports", tags=["reports"])
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True, parents=True)

def _hours(seconds: int) -> float:
    return round(seconds / 3600.0, 2)

@router.get("/schema")
async def schema():
    eff = load_effective_settings()
    return {
        "reports": ["status_summary","throughput","cycle_time","aging_wip"],
        "defaults": {
            "aggregation": "both",
            "business_hours": True,
            "epic_rollup": "full_rollup",
            "timezone": eff["timezone"],
            "window_days": eff["default_window_days"],
            "project_keys": ["MEDA"],   # default testing key
            "max_issues": 25            # default testing cap
        }
    }

@router.get("")
async def list_runs():
    with SessionLocal() as db:
        rows = db.execute(text("SELECT id, started_at, completed_at, status, projects FROM report_runs ORDER BY id DESC")).all()
        return [{"id": r[0], "started_at": r[1], "completed_at": r[2], "status": r[3], "projects": r[4]} for r in rows]

@router.get("/{run_id}")
async def get_run(run_id: int):
    with SessionLocal() as db:
        row = db.execute(text("SELECT * FROM report_runs WHERE id = :i"), {"i": run_id}).mappings().first()
        if not row:
            raise HTTPException(404, "Run not found")
        meta = json.loads(row["meta"]) if row["meta"] else {}
        return {"id": row["id"], "status": row["status"], "meta": meta,
                "csv_issues_path": row["csv_issues_path"], "csv_transitions_path": row["csv_transitions_path"]}

@router.get("/{run_id}/download/{kind}")
async def download_csv(run_id: int, kind: str):
    if kind not in {"issues","transitions","rollups"}:
        raise HTTPException(400, "kind must be issues|transitions|rollups")
    with SessionLocal() as db:
        row = db.execute(text("SELECT * FROM report_runs WHERE id = :i"), {"i": run_id}).mappings().first()
        if not row:
            raise HTTPException(404, "Run not found")
        path = row["csv_issues_path"] if kind == "issues" else (row["csv_transitions_path"] if kind=="transitions" else (json.loads(row["meta"]).get("csv_rollups_path") if row["meta"] else None))
        if not path or not Path(path).exists():
            raise HTTPException(404, "CSV not found")
        return FileResponse(path, media_type="text/csv", filename=Path(path).name)

@router.post("/run", response_model=RunResponse)
async def run_report(req: RunRequest):
    eff = load_effective_settings()
    if not eff["jira_api_token"]:
        raise HTTPException(400, "Jira token missing (DB and .env are both empty). Set it in Admin.")

    with SessionLocal() as db:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        db.execute(
            text(
                "INSERT INTO report_runs (started_at, created_by, projects, jql, time_mode, timezone, agg_mode, epic_rollup, status) "
                "VALUES (:started_at, :created_by, :projects, :jql, :time_mode, :tz, :agg, :epic, 'running')"
            ),
            {
                "started_at": now,
                "created_by": "bootstrap",
                "projects": json.dumps(req.project_keys),
                "jql": req.jql or "",
                "time_mode": "business" if req.business_hours else "24x7",
                "tz": req.timezone or eff["timezone"],
                "agg": req.aggregation,
                "epic": req.epic_rollup,
            }
        )
        db.commit()
        run_id = db.execute(text("SELECT last_insert_rowid()")).scalar_one()

    issues_csv, transitions_csv, rollups_csv, meta = await _execute_run(run_id, req, eff)

    with SessionLocal() as db:
        done = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        meta["csv_rollups_path"] = rollups_csv
        db.execute(
            text("UPDATE report_runs SET completed_at=:done, status='ok', csv_issues_path=:ci, csv_transitions_path=:ct, meta=:meta WHERE id=:i"),
            {"done": done, "ci": issues_csv, "ct": transitions_csv, "meta": json.dumps(meta), "i": run_id}
        )
        db.commit()

    return RunResponse(
        run_id=run_id,
        status="ok",
        csv_issues_url=f"/api/reports/{run_id}/download/issues",
        csv_transitions_url=f"/api/reports/{run_id}/download/transitions",
        meta=meta
    )

async def _execute_run(run_id: int, req: RunRequest, eff: dict):
    window_days = req.window_days or eff["default_window_days"]
    # Order newest first so tests return recent cards
    jql_parts = [f"project in ({','.join(req.project_keys)})", f"updated >= -{window_days}d", "ORDER BY updated DESC"]
    if req.jql:
        jql_parts.insert(2, f"({req.jql})")
    jql = " AND ".join(jql_parts[:2]) + " " + " ".join(jql_parts[2:])

    client = JiraClient(eff["jira_base_url"], eff["jira_email"], eff["jira_api_token"])
    fields = ["summary","issuetype","status","parent","labels","project","created","updated","customfield_10014"]
    issues = await client.search_issues(jql, fields, expand_changelog=False, max_total=(req.max_issues or 25))
    status_catalog = await client.get_status_catalog()  # name -> category

    intervals = []
    per_issue_stats = defaultdict(lambda: {"seconds_bh": 0, "seconds_24": 0, "entries": 0})
    per_issue_bounces = defaultdict(Counter)

    from datetime import timezone as _tz, datetime as _dt
    now_utc = _dt.now(_tz.utc)
    bh_start = eff["business_hours_start"]
    bh_end = eff["business_hours_end"]
    bh_days = eff["business_days"]
    tz = eff["timezone"]

    for issue in issues:
        key = issue["key"]
        histories = await client.get_issue_changelog(key)
        status_changes = []
        for h in histories:
            for item in h.get("items", []):
                if item.get("field") == "status":
                    status_changes.append({"at": parse_jira_ts(h.get("created")), "from": item.get("fromString"), "to": item.get("toString")})
        status_changes = [sc for sc in status_changes if sc["at"] is not None]
        status_changes.sort(key=lambda x: x["at"])

        for idx, change in enumerate(status_changes):
            entered_dt = change["at"]
            exited_dt = status_changes[idx+1]["at"] if idx+1 < len(status_changes) else now_utc
            sec24 = int((exited_dt - entered_dt).total_seconds()) if exited_dt and entered_dt else 0
            secbh = business_seconds_between(entered_dt, exited_dt, tz, bh_start, bh_end, bh_days) if exited_dt and entered_dt else 0
            cat = status_catalog.get(change["to"] or "", "")
            intervals.append({
                "issue_key": key,
                "status_name": change["to"] or "",
                "status_category": cat,
                "entered_at": entered_dt.isoformat(),
                "exited_at": exited_dt.isoformat() if exited_dt else "",
                "duration_seconds_bh": secbh,
                "duration_seconds_24x7": sec24,
            })
            per_issue_stats[key]["seconds_bh"] += secbh
            per_issue_stats[key]["seconds_24"] += sec24
            per_issue_stats[key]["entries"] += 1
            per_issue_bounces[key][change["to"] or ""] += 1

    transitions_path = pathlib.Path("data") / f"run_{run_id}_status_transitions_long.csv"
    with open(transitions_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["run_id","issue_key","status_name","status_category","entered_at","exited_at","duration_seconds_bh","duration_seconds_24x7","interval_index"])
        for idx, iv in enumerate(intervals):
            w.writerow([run_id, iv["issue_key"], iv["status_name"], iv["status_category"], iv["entered_at"], iv["exited_at"], iv["duration_seconds_bh"], iv["duration_seconds_24x7"], idx])

    issues_path = pathlib.Path("data") / f"run_{run_id}_issues_summary.csv"
    with open(issues_path, "w", newline="") as f:
        w = csv.writer(f)
        all_statuses = set()
        for c in per_issue_bounces.values():
            all_statuses.update(c.keys())
        top_statuses = sorted(all_statuses)[:20]
        base_cols = ["run_id","issue_key","project_key","issue_type","summary","status_current","created","updated","epic_key","parent_key","labels","total_time_open_bh_hours","total_time_open_24x7_hours","total_status_entries"]
        bounce_cols = [f"entries_{s}" for s in top_statuses]
        w.writerow(base_cols + bounce_cols)
        for issue in issues:
            fields = issue["fields"]
            key = issue["key"]
            stats = per_issue_stats.get(key, {"seconds_bh":0,"seconds_24":0,"entries":0})
            row = [
                run_id,
                key,
                fields.get("project",{}).get("key",""),
                fields.get("issuetype",{}).get("name",""),
                fields.get("summary",""),
                fields.get("status",{}).get("name",""),
                fields.get("created",""),
                fields.get("updated",""),
                fields.get("customfield_10014","") or "",
                (fields.get("parent") or {}).get("key","") if fields.get("parent") else "",
                ";".join(fields.get("labels") or []),
                _hours(stats["seconds_bh"]),
                _hours(stats["seconds_24"]),
                stats["entries"]
            ]
            counts = per_issue_bounces.get(key, {})
            row += [counts.get(s, 0) for s in top_statuses]
            w.writerow(row)

    epic_totals = defaultdict(lambda: {"seconds_bh":0,"seconds_24":0,"entries":0,"issues":set()})
    parent_totals = defaultdict(lambda: {"seconds_bh":0,"seconds_24":0,"entries":0,"issues":set(),"epic":""})

    for issue in issues:
        key = issue["key"]
        fields = issue["fields"]
        epic = fields.get("customfield_10014","") or ""
        parent = (fields.get("parent") or {}).get("key","") if fields.get("parent") else ""
        st = per_issue_stats.get(key, {"seconds_bh":0,"seconds_24":0,"entries":0})
        if epic:
            epic_totals[epic]["seconds_bh"] += st["seconds_bh"]
            epic_totals[epic]["seconds_24"] += st["seconds_24"]
            epic_totals[epic]["entries"] += st["entries"]
            epic_totals[epic]["issues"].add(key)
        if parent:
            parent_totals[parent]["seconds_bh"] += st["seconds_bh"]
            parent_totals[parent]["seconds_24"] += st["seconds_24"]
            parent_totals[parent]["entries"] += st["entries"]
            parent_totals[parent]["issues"].add(key)
            parent_totals[parent]["epic"] = epic

    rollups_path = pathlib.Path("data") / f"run_{run_id}_rollups.csv"
    with open(rollups_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["run_id","level","entity_key","epic_key","parent_key","children_count","total_time_bh_hours","total_time_24x7_hours","total_status_entries"])
        for parent_key, agg in parent_totals.items():
            w.writerow([run_id,"parent","", "", parent_key, len(agg["issues"]), _hours(agg["seconds_bh"]), _hours(agg["seconds_24"]), agg["entries"]])
        for epic_key, agg in epic_totals.items():
            w.writerow([run_id,"epic",epic_key, epic_key, "", len(agg["issues"]), _hours(agg["seconds_bh"]), _hours(agg["seconds_24"]), agg["entries"]])

    meta = {"issues": len(issues), "intervals": len(intervals), "jql": jql}
    return str(issues_path), str(transitions_path), str(rollups_path), meta
