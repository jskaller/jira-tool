"""
Lightweight compatibility shim for exporting a SQLAlchemy Base from app.db.
Imports your project's Base if it exists; otherwise, provides a local fallback.
"""
from __future__ import annotations

try:
    # Common place projects define their Base
    from app.db.database import Base  # type: ignore
except Exception:
    try:
        from app.db.models import Base  # type: ignore
    except Exception:
        # Fallback to a local declarative base to avoid import errors.
        from sqlalchemy.orm import declarative_base
        Base = declarative_base()

__all__ = ["Base"]
