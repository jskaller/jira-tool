import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .core.config import get_settings
from .db.database import init_db, get_sessionmaker
from .db.models import User
from .core.security import hash_password
from sqlalchemy import select
from .api import auth, me, admin, reports

app = FastAPI(title="Jira Tools", version="0.0.1" )

# CORS
settings = get_settings()
origins = [o.strip() for o in settings.frontend_origins if o]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def on_startup():
    await init_db()
    # Bootstrap admin if no users
    Session = get_sessionmaker()
    async with Session() as session:
        res = await session.execute(select(User))
        any_user = res.first()
        if not any_user:
            u = User(email=settings.bootstrap_admin_email, name="Admin", role="admin", password_hash=hash_password(settings.bootstrap_admin_password))
            session.add(u)
            await session.commit()
            print("[bootstrap] Created admin user:", settings.bootstrap_admin_email)

app.include_router(auth.router, prefix="/api")
app.include_router(me.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(reports.router, prefix="/api")

@app.get("/api/health")
async def health():
    return {"ok": True}

@app.get("/api/version")
async def version():
    return {"version": app.version}
