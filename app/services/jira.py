import httpx
from typing import Dict, Any, List, Optional
from urllib.parse import urlencode

class JiraClient:
    def __init__(self, base_url: str, email: str, api_token: str):
        self.base = base_url.rstrip("/")
        self.auth = (email, api_token)
        self.headers = {"Accept": "application/json"}

    async def test_connection(self) -> bool:
        if not self.auth[1]:
            return False
        url = f"{self.base}/rest/api/3/myself"
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.get(url, auth=self.auth, headers=self.headers)
            return r.status_code == 200

    async def search_issues(self, jql: str, fields: List[str], expand_changelog: bool=False, max_total: Optional[int]=None):
        start_at = 0
        max_results = 100
        issues: List[Dict[str, Any]] = []
        async with httpx.AsyncClient(timeout=60.0) as client:
            while True:
                if max_total is not None:
                    remaining = max_total - len(issues)
                    if remaining <= 0:
                        break
                    max_results = min(max_results, max(1, remaining))
                params = {
                    "jql": jql,
                    "startAt": start_at,
                    "maxResults": max_results,
                    "fields": ",".join(fields),
                    "expand": "changelog" if expand_changelog else None
                }
                url = f"{self.base}/rest/api/3/search?{urlencode({k:v for k,v in params.items() if v is not None})}"
                r = await client.get(url, auth=self.auth, headers=self.headers)
                r.raise_for_status()
                data = r.json()
                issues.extend(data.get("issues", []))
                if start_at + max_results >= data.get("total", 0):
                    break
                start_at += max_results
        if max_total is not None and len(issues) > max_total:
            issues = issues[:max_total]
        return issues

    async def get_issue_changelog(self, key: str):
        start_at = 0
        max_results = 100
        histories: List[Dict[str, Any]] = []
        async with httpx.AsyncClient(timeout=60.0) as client:
            while True:
                url = f"{self.base}/rest/api/3/issue/{key}/changelog?startAt={start_at}&maxResults={max_results}"
                r = await client.get(url, auth=self.auth, headers=self.headers)
                r.raise_for_status()
                data = r.json()
                histories.extend(data.get("values", []))
                if start_at + max_results >= data.get("total", 0):
                    break
                start_at += max_results
        return histories

    async def get_status_catalog(self) -> Dict[str, str]:
        url = f"{self.base}/rest/api/3/status"
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.get(url, auth=self.auth, headers=self.headers)
            r.raise_for_status()
            arr = r.json()
        out: Dict[str, str] = {}
        for s in arr:
            name = s.get("name") or ""
            cat = ((s.get("statusCategory") or {}).get("name")) or ""
            if name:
                out[name] = cat
        return out
