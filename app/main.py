
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from .config import settings
from .db import init_db
from .routers import reports, admin
from .effective import ensure_settings_row, bootstrap_token_from_env_if_empty

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

app.include_router(reports.router)
app.include_router(admin.router)

# Serve UI directly at / (no redirect to /ui)
app.mount("/", StaticFiles(directory="backend/web", html=True), name="web")

@app.on_event("startup")
async def _startup():
    init_db()
    ensure_settings_row()
    bootstrap_token_from_env_if_empty()
