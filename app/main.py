from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import settings
from .db import init_db, SessionLocal
from .routers import reports, admin, auth
from .effective import ensure_settings_row, bootstrap_token_from_env_if_empty
from .models import User
from passlib.hash import bcrypt

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
app.include_router(reports.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(auth.router, prefix="/api")  # ✅ now under /api/auth

# Serve static UI at root (no /ui redirect)
app.mount("/", StaticFiles(directory="backend/web", html=True), name="web")
app.mount("/ui", StaticFiles(directory="backend/web", html=True), name="ui")

@app.on_event("startup")
async def _startup():
    init_db()
    ensure_settings_row()
    bootstrap_token_from_env_if_empty()
    # Bootstrap admin user if DB has none
    with SessionLocal() as db:
        if db.query(User).count() == 0:
            u = User(
                email=settings.bootstrap_admin_email,
                password_hash=bcrypt.hash(settings.bootstrap_admin_password),
                is_admin=True,
            )
            db.add(u)
            db.commit()
