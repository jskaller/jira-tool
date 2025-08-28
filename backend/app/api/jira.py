from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from ..api.deps import current_admin
from ..db.database import get_sessionmaker
from ..db.jira_models import BaseJira, JiraIssue, JiraTransition
from sqlalchemy import delete
import httpx
import json
from datetime import datetime
import re

router = APIRouter(prefix="/jira", tags=["jira"])

class IngestRequest(BaseModel):
    jira_base_url: str
    jira_email: str
    jira_api_token: str
    projects: List[str] = Field(default_factory=list)
    labels: List[str] = Field(default_factory=list)
    jql: str = ""
    updated_window_days: int = 180
    max_issues: int = 25000

# Heuristic for a Jira project key (all caps + digits/underscores, starting with a letter)
KEY_REGEX = re.compile(r'^[A-Z][A-Z0-9_]+$')

def _quote(s: str) -> str:
    s = s.replace('"', '\"')
    return f'"{s}"'

def _build_jql(req: IngestRequest) -> str:
    clauses = []
    # Projects
    if req.projects:
        parts = []
        for p in req.projects:
            p = (p or "").strip()
            if not p:
                continue
            # If it's all digits, treat as project ID
            if p.isdigit():
                parts.append(p)
            elif KEY_REGEX.match(p):
                parts.append(p)  # treat as KEY
            else:
                parts.append(_quote(p))  # treat as NAME
        if parts:
            clauses.append(f"project in ({', '.join(parts)})")
    # Labels
    if req.labels:
        parts = []
        for l in req.labels:
            l = (l or "").strip()
            if not l:
                continue
            parts.append(_quote(l) if " " in l else l)
        if parts:
            clauses.append(f"labels in ({', '.join(parts)})")
    # Updated window
    if req.updated_window_days and req.updated_window_days > 0:
        clauses.append(f"updated >= -{req.updated_window_days}d")
    # Extra JQL
    if req.jql.strip():
        clauses.append(f"({req.jql.strip()})")
    jql = " and ".join(clauses) if clauses else ""
    if "order by" not in jql.lower():
        jql = (jql + " order by updated desc").strip()
    return jql or "order by updated desc"

async def _ensure_tables():
    # Create the jira_issues / jira_transitions tables using the current bind
    Session = get_sessionmaker()
    async with Session() as session:
        def _create(sync_session):
            bind = sync_session.get_bind()
            BaseJira.metadata.create_all(bind=bind)
        await session.run_sync(_create)

def _parse_issue_fields(issue: Dict[str, Any]) -> Dict[str, Any]:
    f = issue.get("fields") or {}
    key = issue.get("key", "")
    project_key = (f.get("project") or {}).get("key") or (key.split("-")[0] if "-" in key else "")
    issue_type = (f.get("issuetype") or {}).get("name") or ""
    summary = f.get("summary") or ""
    status = (f.get("status") or {}).get("name") or ""
    assignee = (f.get("assignee") or {}).get("displayName") or ""
    parent_key = (f.get("parent") or {}).get("key") or ""
    epic_key = (f.get("epic") or {}).get("key") or ""
    def _dt(s):
        if not s: return None
        try:
            return datetime.fromisoformat(s.replace("Z","+00:00"))
        except Exception:
            return None
    return {
        "issue_id": str(issue.get("id")),
        "key": key,
        "project_key": project_key,
        "issue_type": issue_type,
        "summary": summary,
        "status": status,
        "assignee": assignee,
        "parent_key": parent_key,
        "epic_key": epic_key,
        "created": _dt((f.get("created") or "")),
        "updated": _dt((f.get("updated") or "")),
    }

def _extract_transitions(issue: Dict[str, Any]):
    hist = (issue.get("changelog") or {}).get("histories") or []
    out = []
    for h in hist:
        created = h.get("created")
        try:
            when = datetime.fromisoformat(created.replace("Z","+00:00"))
        except Exception:
            continue
        author = (h.get("author") or {}).get("displayName") or ""
        for it in h.get("items", []):
            if (it.get("field") or "").lower() == "status":
                out.append({
                    "when": when,
                    "author": author,
                    "from_status": it.get("fromString") or "",
                    "to_status": it.get("toString") or "",
                })
    out.sort(key=lambda x: x["when"])
    return out

@router.get("/projects")
async def list_projects(
    base_url: str = Query(..., alias="base_url"),
    email: str = Query(..., alias="email"),
    token: str = Query(..., alias="token"),
    _=Depends(current_admin)
):
    base = base_url.rstrip("/")
    url = f"{base}/rest/api/3/project/search"
    headers = {"Accept": "application/json"}
    auth = (email, token)
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, headers=headers, auth=auth, params={"maxResults": 1000})
        if r.status_code == 401:
            raise HTTPException(status_code=401, detail="Jira authentication failed (401). Check email/token.")
        if r.status_code >= 400:
            raise HTTPException(status_code=r.status_code, detail=f"Jira error: {r.text[:500]}")
        data = r.json() or {}
        values = data.get("values") or data.get("projects") or data.get("items") or []
        out = []
        for p in values:
            out.append({
                "id": p.get("id"),
                "key": p.get("key"),
                "name": p.get("name"),
                "projectTypeKey": p.get("projectTypeKey") or p.get("style"),
                "archived": p.get("archived", False),
                "simplified": p.get("simplified", None)
            })
        return {"ok": True, "count": len(out), "projects": out}

@router.get("/jql-check")
async def jql_check(
    base_url: str = Query(..., alias="base_url"),
    email: str = Query(..., alias="email"),
    token: str = Query(..., alias="token"),
    jql: str = Query(..., alias="jql"),
    _=Depends(current_admin)
):
    base = base_url.rstrip("/")
    url = f"{base}/rest/api/3/search"
    headers = {"Accept": "application/json"}
    auth = (email, token)
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, headers=headers, auth=auth, params={"jql": jql, "maxResults": 0})
        if r.status_code >= 400:
            raise HTTPException(status_code=r.status_code, detail=f"Jira error (status {r.status_code}) for JQL: {jql} :: {r.text[:500]}")
        return {"ok": True, "jql": jql}

@router.post("/ingest")
async def ingest(req: IngestRequest, _=Depends(current_admin)):
    if not (req.jira_base_url and req.jira_email and req.jira_api_token):
        raise HTTPException(status_code=400, detail="jira_base_url, jira_email, and jira_api_token are required")
    await _ensure_tables()

    jql = _build_jql(req)
    base = req.jira_base_url.rstrip("/")
    url = f"{base}/rest/api/3/search"
    headers = {"Accept": "application/json"}
    auth = (req.jira_email, req.jira_api_token)

    max_results = 100
    start_at = 0
    total = None
    fetched = 0
    issues_saved = 0
    transitions_saved = 0

    Session = get_sessionmaker()
    async with httpx.AsyncClient(timeout=30) as client:
        while True:
            params = {
                "jql": jql,
                "startAt": start_at,
                "maxResults": max_results,
                "expand": "changelog"
            }
            r = await client.get(url, headers=headers, params=params, auth=auth)
            if r.status_code >= 400:
                raise HTTPException(status_code=r.status_code, detail=f"Jira error (status {r.status_code}) for JQL: {jql} :: {r.text[:500]}")
            data = r.json()
            issues = data.get("issues", [])
            total = data.get("total", total)
            if not issues:
                break

            async with Session() as session:
                for issue in issues:
                    fields = _parse_issue_fields(issue)
                    raw_json = json.dumps(issue)
                    await session.execute(delete(JiraIssue).where(JiraIssue.issue_id == fields["issue_id"]))
                    session.add(JiraIssue(**fields, raw_json=raw_json))
                    issues_saved += 1

                    await session.execute(delete(JiraTransition).where(JiraTransition.issue_id == fields["issue_id"]))
                    for t in _extract_transitions(issue):
                        session.add(JiraTransition(
                            issue_id=fields["issue_id"],
                            issue_key=fields["key"],
                            when=t["when"],
                            author=t["author"],
                            from_status=t["from_status"],
                            to_status=t["to_status"],
                        ))
                        transitions_saved += 1
                await session.commit()

            fetched += len(issues)
            if fetched >= req.max_issues:
                break
            start_at += len(issues)
            if total is not None and start_at >= total:
                break

    return {
        "ok": True,
        "jql": jql,
        "fetched": fetched,
        "issues_saved": issues_saved,
        "transitions_saved": transitions_saved,
        "total_reported_by_jira": total
    }
