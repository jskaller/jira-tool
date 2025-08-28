# Zip 0005 patch: add greenlet dependency

Fixes:
- `ValueError: the greenlet library is required to use this function. No module named 'greenlet'` during app startup.

What changed:
- Added `greenlet==3.0.3` to `backend/requirements.txt`.

Apply:
```bash
unzip ~/Downloads/jira-reporting-0005.zip
git add backend/requirements.txt README.md
git commit -m "0005: Add greenlet dependency for SQLAlchemy asyncio"
```

Then reinstall deps and run:
```bash
cd backend
source .venv/bin/activate 2>/dev/null || true
pip install -r requirements.txt
./run.sh
```
