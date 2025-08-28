from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from ..api.deps import current_admin
from ..db.database import get_sessionmaker
from ..db.jira_models import BaseJira, JiraIssue, JiraTransition
from ..core.config import get_settings
from sqlalchemy import delete
import httpx
import json
from datetime import datetime
import re

router = APIRouter(prefix="/jira", tags=["jira"])

class IngestRequest(BaseModel):
    jira_base_url: Optional[str] = None
    jira_email: Optional[str] = None
    jira_api_token: Optional[str] = None
    projects: List[str] = Field(default_factory=list)
    labels: List[str] = Field(default_factory=list)
    jql: str = ""
    updated_window_days: int = 180
    max_issues: int = 25000

KEY_REGEX = re.compile(r'^[A-Z][A-Z0-9_]+$')

def _quote(s: str) -> str:
    s = s.replace('"', '\\"')
    return f'"{s}"'

def _build_jql(req: IngestRequest) -> str:
    clauses = []
    if req.projects:
        parts = []
        for p in req.projects:
            p = (p or "").strip()
            if not p:
                continue
            if p.isdigit():
                parts.append(p)       # numeric ID
            elif KEY_REGEX.match(p):
                parts.append(p)       # key
            else:
                parts.append(_quote(p))  # name
        if parts:
            clauses.append(f"project in ({', '.join(parts)})")
    if req.labels:
        parts = []
        for l in req.labels:
            l = (l or "").strip()
            if not l: continue
            parts.append(_quote(l) if " " in l else l)
        if parts:
            clauses.append(f"labels in ({', '.join(parts)})")
    if req.updated_window_days and req.updated_window_days > 0:
        clauses.append(f"updated >= -{req.updated_window_days}d")
    if req.jql.strip():
        clauses.append(f"({req.jql.strip()})")
    jql = " and ".join(clauses) if clauses else ""
    if "order by" not in jql.lower():
        jql = (jql + " order by updated desc").strip()
    return jql or "order by updated desc"

async def _ensure_tables():
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

async def _client():
    return httpx.AsyncClient(timeout=30)

def _resolve_credentials(req: IngestRequest):
    settings = get_settings()
    base_url = (req.jira_base_url or settings.jira_base_url or "").rstrip("/")
    email = req.jira_email or settings.jira_email
    token = req.jira_api_token or settings.jira_api_token
    if not (base_url and email and token):
        raise HTTPException(status_code=400, detail="jira_base_url, jira_email, and jira_api_token are required (either in request or saved settings).")
    return base_url, email, token

def _resolve_from_params(base_url: Optional[str], email: Optional[str], token: Optional[str]):
    s = get_settings()
    base = (base_url or s.jira_base_url or "").rstrip("/")
    em = email or s.jira_email
    tk = token or s.jira_api_token
    if not (base and em and tk):
        raise HTTPException(status_code=400, detail="Missing Jira credentials. Provide base_url, email, token or save them in Admin → Settings.")
    return base, em, tk

@router.get("/whoami")
async def whoami(base_url: Optional[str] = None, email: Optional[str] = None, token: Optional[str] = None, _=Depends(current_admin)):
    base, em, tk = _resolve_from_params(base_url, email, token)
    url = f"{base}/rest/api/3/myself"
    headers = {"Accept": "application/json"}
    async with await _client() as client:
        r = await client.get(url, headers=headers, auth=(em, tk))
        if r.status_code >= 400:
            raise HTTPException(status_code=r.status_code, detail=f"Jira error: {r.text[:500]}")
        data = r.json()
        return {"ok": True, "accountId": data.get("accountId"), "displayName": data.get("displayName"), "raw": data}

@router.get("/project")
async def get_project(base_url: Optional[str] = None, email: Optional[str] = None, token: Optional[str] = None, id_or_key: str = "", _=Depends(current_admin)):
    base, em, tk = _resolve_from_params(base_url, email, token)
    if not id_or_key:
        raise HTTPException(status_code=400, detail="id_or_key is required")
    url = f"{base}/rest/api/3/project/{id_or_key}"
    headers = {"Accept": "application/json"}
    async with await _client() as client:
        r = await client.get(url, headers=headers, auth=(em, tk))
        if r.status_code >= 400:
            raise HTTPException(status_code=r.status_code, detail=f"Jira error: {r.text[:500]}")
        return r.json()

@router.get("/projects")
async def list_projects(base_url: Optional[str] = None, email: Optional[str] = None, token: Optional[str] = None, _=Depends(current_admin)):
    base, em, tk = _resolve_from_params(base_url, email, token)
    url = f"{base}/rest/api/3/project/search"
    headers = {"Accept": "application/json"}
    async with await _client() as client:
        r = await client.get(url, headers=headers, auth=(em, tk), params={"maxResults": 1000})
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
async def jql_check(base_url: Optional[str] = None, email: Optional[str] = None, token: Optional[str] = None, jql: str = "", _=Depends(current_admin)):
    base, em, tk = _resolve_from_params(base_url, email, token)
    if not jql:
        raise HTTPException(status_code=400, detail="jql is required")
    url = f"{base}/rest/api/3/search"
    headers = {"Accept": "application/json"}
    async with await _client() as client:
        r = await client.get(url, headers=headers, auth=(em, tk), params={"jql": jql, "maxResults": 0})
        if r.status_code >= 400:
            raise HTTPException(status_code=r.status_code, detail=f"Jira error (status {r.status_code}) for JQL: {jql} :: {r.text[:500]}")
        return {"ok": True, "jql": jql}

@router.post("/ingest")
async def ingest(req: IngestRequest, _=Depends(current_admin)):
    base, email, token = _resolve_credentials(req)
    await _ensure_tables()

    jql = _build_jql(req)
    url = f"{base}/rest/api/3/search"
    headers = {"Accept": "application/json"}

    max_results = 100
    start_at = 0
    total = None
    fetched = 0
    issues_saved = 0
    transitions_saved = 0

    Session = get_sessionmaker()
    async with await _client() as client:
        while True:
            params = {"jql": jql, "startAt": start_at, "maxResults": max_results, "expand": "changelog"}
            r = await client.get(url, headers=headers, params=params, auth=(email, token))
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

    return {"ok": True, "jql": jql, "fetched": fetched, "issues_saved": issues_saved, "transitions_saved": transitions_saved, "total_reported_by_jira": total}
