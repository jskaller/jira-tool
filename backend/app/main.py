from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .api import auth, admin, reports, health
from .db.database import init_db
from .core.config import get_settings

app = FastAPI(title="Jira Tools")

settings = get_settings()

@app.on_event("startup")
async def on_startup():
    await init_db()

# API routers
app.include_router(auth.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(reports.router, prefix="/api")
app.include_router(health.router, prefix="/api")

# Static UI
app.mount("/", StaticFiles(directory="web", html=True), name="web")
