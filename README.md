# Jira Tools (Zip 0003)

This patch zip provides an updated `backend/run.sh` that **prefers Python 3.12/3.11 and refuses 3.13**, fixing the pydantic-core build error on macOS when Python 3.13 is the default.

## How to apply
Unzip this file over your existing repo so that `backend/run.sh` is replaced.

```bash
unzip ~/Downloads/jira-reporting-0003.zip -d your/repo/root
git add backend/run.sh README.md
git commit -m "0003: Use Python 3.12/3.11 in run.sh to avoid PyO3 build on 3.13"
```

Then run:

```bash
cd backend
./run.sh
# open http://127.0.0.1:8000
```

### Install Python 3.12 (macOS/Homebrew)

```bash
brew install python@3.12
# optional convenience:
ln -s /opt/homebrew/bin/python3.12 /usr/local/bin/python3.12 2>/dev/null || true
```
