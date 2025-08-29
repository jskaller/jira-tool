"""Compatibility shim for importing the shared SQLAlchemy Base.

This tries several common module locations where your project might define
the declarative Base. If none are found, it falls back to creating a local
Base so imports don't crash. If you do have a shared Base elsewhere, feel
free to replace this file with a single import from that location.
"""
from __future__ import annotations

# Do not add runtime-only dependencies here to keep import-time simple/robust.
try:
    # Most common spot (e.g., app/db/database.py -> Base)
    from .database import Base  # type: ignore
except Exception:
    try:
        # Some projects keep Base in models.py
        from .models import Base  # type: ignore
    except Exception:
        try:
            # Or a different module name
            from .engine import Base  # type: ignore
        except Exception:
            # Last resort: create a local Base so imports don't fail.
            # NOTE: If this is used, the Report model will be on its own
            # metadata. If you have a central Base elsewhere, update the
            # imports above to point to it.
            from sqlalchemy.orm import declarative_base
            Base = declarative_base()  # type: ignore
