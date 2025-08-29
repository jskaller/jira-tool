from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from .config import settings
from .db import init_db
from .routers import reports, admin
from .effective import ensure_settings_row, bootstrap_token_from_env_if_empty
from pathlib import Path

app = FastAPI(title="Jira Reporting")

if settings.frontend_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.frontend_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

@app.get("/health")
async def health():
    return {"ok": True}

# API routers
app.include_router(reports.router)
app.include_router(admin.router)

# Serve built React app if present
dist_dir = Path("frontend/dist")
if dist_dir.exists():
    app.mount("/", StaticFiles(directory=dist_dir, html=True), name="ui")
else:
    # fallback: serve raw public index.html for dev instructions
    app.mount("/ui", StaticFiles(directory="frontend", html=True), name="ui")
    @app.get("/")
    async def root_redirect():
        return RedirectResponse(url="/ui/")

@app.on_event("startup")
async def _startup():
    init_db()
    ensure_settings_row()
    bootstrap_token_from_env_if_empty()
