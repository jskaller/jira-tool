# Zip 0006 patch: pin bcrypt to 4.0.1

Fixes the runtime warning:
`(trapped) error reading bcrypt version ... AttributeError: module 'bcrypt' has no attribute '__about__'`

What changed:
- Added `bcrypt==4.0.1` to `backend/requirements.txt` (passlib 1.7.4 works fine with this version).

Apply:
```bash
unzip ~/Downloads/jira-reporting-0006.zip
git add backend/requirements.txt README.md
git commit -m "0006: Pin bcrypt==4.0.1 to silence passlib warning"
```

Reinstall deps and run:
```bash
cd backend
source .venv/bin/activate 2>/dev/null || true
pip install --upgrade --force-reinstall -r requirements.txt
./run.sh
```
