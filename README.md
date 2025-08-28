# Zip 0010: Password change & basic user admin

**Why:** `.env` values `BOOTSTRAP_ADMIN_EMAIL` and `BOOTSTRAP_ADMIN_PASSWORD` are only used the *first time* the app starts (when there are no users). After the admin user exists, changing `.env` won't change credentials.

**What this adds**
- `POST /api/users/me/password` — change your own password (requires current password).
- `GET /api/users/admin` — list users (admin only).
- `POST /api/users/admin` — create a new user (admin only).
- UI: Admin tab now has:
  - "Change My Password" form
  - Simple Users section: create user + list users

**Apply**
```bash
unzip ~/Downloads/jira-reporting-0010.zip
git add backend/app/api/users.py backend/app/main.py backend/web/index.html README.md
git commit -m "0010: Add password change and basic user admin; clarify .env bootstrap behavior"
```

**Tip:** If you really want to re-bootstrap from `.env`, delete `backend/app.db` (you'll lose data) and restart. Otherwise, use the new Admin forms.
