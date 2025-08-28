# Zip 0007: Robust auth (cookie + header token)

- `/api/auth/login` now returns `{ token, user }` and still sets the session cookie.
- Backend accepts session via cookie **or** `Authorization: Bearer <token>` **or** `X-Session` header (and as `?x_session=` for CSV downloads).
- Static UI stores the token in `sessionStorage` and sends it on all API calls for reliability across browsers/hosts.

Apply:
```bash
unzip ~/Downloads/jira-reporting-0007.zip
git add backend/app/api/auth.py backend/app/api/deps.py backend/web/index.html README.md
git commit -m "0007: Add header-based auth fallback (X-Session/Bearer) and UI support"
```

Restart backend and re-login on the Login tab.
