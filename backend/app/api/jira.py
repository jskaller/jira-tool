from fastapi import APIRouter, Depends, HTTPException, Query, Body
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Tuple
from ..api.deps import current_admin
from ..db.database import get_sessionmaker
from ..db.jira_models import BaseJira, JiraIssue, JiraTransition
from ..core.config import get_settings
from sqlalchemy import delete, text
import httpx
import json
from datetime import datetime
import re
import base64
import hashlib

try:
    from cryptography.fernet import Fernet
    HAVE_CRYPTO = True
except Exception:
    HAVE_CRYPTO = False

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

SETTINGS_SYNONYMS = {
    "base_url": ["jira_base_url", "base_url", "jira_url", "url"],
    "email": ["jira_email", "email", "username", "user_email"],
    "token": ["jira_api_token", "api_token", "jira_token", "jira_api_token_encrypted", "jira_token_encrypted", "token", "encrypted_token"],
}

def _first_present(row: Dict[str, Any], names: List[str]):
    for n in names:
        if n in row and row[n]:
            return n, row[n]
    return None, None

def _fernet_from_secret(secret: str):
    if not HAVE_CRYPTO:
        return None
    # Derive a stable Fernet key from APP_SECRET (sha256 -> urlsafe base64)
    h = hashlib.sha256((secret or "").encode()).digest()
    key = base64.urlsafe_b64encode(h)
    return Fernet(key)

def _maybe_decrypt(token_value: str, token_column: Optional[str]) -> str:
    if not token_value:
        return token_value
    looks_encrypted = False
    if token_column and "encrypt" in token_column.lower():
        looks_encrypted = True
    if token_value.startswith("gAAAAA"):  # typical Fernet prefix
        looks_encrypted = True
    if looks_encrypted and HAVE_CRYPTO:
        try:
            f = _fernet_from_secret(get_settings().app_secret)
            if f:
                return f.decrypt(token_value.encode()).decode()
        except Exception:
            pass
    return token_value

async def _scan_db_for_settings_candidates() -> List[Dict[str, Any]]:
    Session = get_sessionmaker()
    async with Session() as session:
        def _sync_scan(sync_session):
            res = []
            bind = sync_session.get_bind()
            with bind.connect() as conn:
                tables = [r[0] for r in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()]
                for t in tables:
                    try:
                        cols = [row[1] for row in conn.execute(text(f"PRAGMA table_info({t})")).fetchall()]
                        colset = set(cols)
                        if not any(name in colset for names in SETTINGS_SYNONYMS.values() for name in names):
                            continue
                        row = conn.execute(text(f"SELECT * FROM {t} ORDER BY rowid DESC LIMIT 1")).mappings().fetchone()
                        if not row:
                            continue
                        rowd = dict(row)
                        b_name, b_val = _first_present(rowd, SETTINGS_SYNONYMS["base_url"])
                        e_name, e_val = _first_present(rowd, SETTINGS_SYNONYMS["email"])
                        t_name, t_val = _first_present(rowd, SETTINGS_SYNONYMS["token"])
                        if any([b_val, e_val, t_val]):
                            res.append({
                                "table": t,
                                "columns": cols,
                                "base_url": {"column": b_name, "value": b_val},
                                "email": {"column": e_name, "value": e_val},
                                "token": {"column": t_name, "value": t_val},
                            })
                    except Exception:
                        continue
            return res
        return await session.run_sync(_sync_scan)

async def _load_saved_jira_settings_from_db() -> Tuple[Optional[str], Optional[str], Optional[str], Dict[str, Any]]:
    candidates = await _scan_db_for_settings_candidates()
    meta = {"candidates": candidates}
    def score(c):
        return sum(1 for k in ["base_url", "email", "token"] if c[k]["value"])
    best = None
    if candidates:
        candidates.sort(key=score, reverse=True)
        best = candidates[0]
    if best:
        token_raw = best["token"]["value"]
        token_col = best["token"]["column"]
        token_final = _maybe_decrypt(token_raw, token_col) if token_raw else None
        return best["base_url"]["value"], best["email"]["value"], token_final, meta
    return None, None, None, meta

def _mask_token(token: Optional[str]) -> Dict[str, Any]:
    if not token:
        return {"present": False, "len": 0, "preview": ""}
    return {"present": True, "len": len(token), "preview": (token[:4] + "…" if len(token) > 4 else token)}

async def _resolve_meta_only(base_url: Optional[str], email: Optional[str], token: Optional[str]) -> Tuple[Optional[str], Optional[str], Optional[str], Dict[str, Any]]:
    meta: Dict[str, Any] = {"sources": {}, "env": {}, "db": {}}
    s = get_settings()

    base = (base_url or "").rstrip("/")
    em = email or ""
    tk = token or ""
    meta["sources"]["params"] = {"base_url": bool(base_url), "email": bool(email), "token": bool(token)}

    db_base, db_email, db_token, db_meta = await _load_saved_jira_settings_from_db()
    meta["db"] = db_meta
    if not base: base = (db_base or "")
    if not em: em = (db_email or "")
    if not tk: tk = (db_token or "")

    if not base: base = (s.jira_base_url or "")
    if not em: em = (s.jira_email or "")
    if not tk: tk = (s.jira_api_token or "")

    base = base.rstrip("/")
    meta["sources"]["env"] = {"used": bool(s.jira_base_url or s.jira_email or s.jira_api_token)}
    meta["resolved"] = {"base_url": base, "email": em, "token": _mask_token(tk)}
    meta["myself_url"] = f"{base}/rest/api/3/myself" if base else None
    ok = bool(base and em and tk)
    meta["ok"] = ok
    return (base if ok else None), (em if ok else None), (tk if ok else None), meta

async def _resolve_strict(base_url: Optional[str], email: Optional[str], token: Optional[str]) -> Tuple[str, str, str]:
    base, em, tk, meta = await _resolve_meta_only(base_url, email, token)
    if not (base and em and tk):
        raise HTTPException(status_code=400, detail="Missing Jira credentials. Provide base_url, email, token or save them in Admin → Settings.")
    return base, em, tk

# ------------------- Diagnostics ---------------------------------------------
@router.get("/diagnostics/creds")
async def creds_diag(
    base_url: Optional[str] = Query(default=None),
    email: Optional[str] = Query(default=None),
    token: Optional[str] = Query(default=None),
    _=Depends(current_admin),
):
    _, _, _, meta = await _resolve_meta_only(base_url, email, token)
    return {"ok": meta["ok"], "meta": meta}

@router.get("/diagnostics/db-schema")
async def db_schema(_=Depends(current_admin)):
    cands = await _scan_db_for_settings_candidates()
    return {"ok": True, "candidates": cands}

@router.post("/diagnostics/save-token")
async def diag_save_token(
    token: str = Body(..., embed=True),
    base_url: Optional[str] = Body(default=None),
    email: Optional[str] = Body(default=None),
    _=Depends(current_admin),
):
    """
    Write the provided token into the settings table under any known '*_encrypted' token column.
    Also optionally update base_url/email if provided. Returns updated diagnostics.
    """
    Session = get_sessionmaker()
    s = get_settings()

    enc = token
    if HAVE_CRYPTO:
        try:
            f = _fernet_from_secret(s.app_secret)
            if f:
                enc = f.encrypt(token.encode()).decode()
        except Exception:
            pass

    async with Session() as session:
        def _sync_write(sync_session):
            bind = sync_session.get_bind()
            with bind.connect() as conn:
                # ensure settings table exists
                tables = [r[0] for r in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()]
                if "settings" not in tables:
                    conn.execute(text("CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY AUTOINCREMENT, jira_base_url TEXT, jira_email TEXT, jira_token_encrypted TEXT)"))
                cols = [row[1] for row in conn.execute(text("PRAGMA table_info(settings)")).fetchall()]
                token_cols = [c for c in cols if c in ("jira_api_token_encrypted", "jira_token_encrypted", "encrypted_token", "api_token")]
                token_col = token_cols[0] if token_cols else "jira_token_encrypted"
                if token_col not in cols:
                    conn.execute(text(f"ALTER TABLE settings ADD COLUMN {token_col} TEXT"))
                    cols.append(token_col)
                row = conn.execute(text("SELECT rowid, * FROM settings ORDER BY rowid DESC LIMIT 1")).fetchone()
                if row:
                    sets = []
                    params = {}
                    if base_url is not None and "jira_base_url" in cols:
                        sets.append("jira_base_url=:b")
                        params["b"] = base_url
                    if email is not None and "jira_email" in cols:
                        sets.append("jira_email=:e")
                        params["e"] = email
                    sets.append(f"{token_col}=:t")
                    params["t"] = enc
                    if sets:
                        conn.execute(text(f"UPDATE settings SET {', '.join(sets)} WHERE rowid=:rid"), {"rid": row[0], **params})
                else:
                    conn.execute(text("INSERT INTO settings (jira_base_url, jira_email, {tc}) VALUES (:b, :e, :t)".format(tc=token_col)),
                                 {"b": base_url or "", "e": email or "", "t": enc})
            return True
        await session.run_sync(_sync_write)

    _, _, _, meta = await _resolve_meta_only(base_url=None, email=None, token=None)
    return {"ok": meta["ok"], "meta": meta}

# ------------------- Jira endpoints ------------------------------------------
async def _client():
    return httpx.AsyncClient(timeout=30)

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

@router.get("/whoami")
async def whoami(base_url: Optional[str] = None, email: Optional[str] = None, token: Optional[str] = None, _=Depends(current_admin)):
    base, em, tk = await _resolve_strict(base_url, email, token)
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
    base, em, tk = await _resolve_strict(base_url, email, token)
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
    base, em, tk = await _resolve_strict(base_url, email, token)
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
    base, em, tk = await _resolve_strict(base_url, email, token)
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
    base, email, token = await _resolve_strict(req.jira_base_url, req.jira_email, req.jira_api_token)
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
