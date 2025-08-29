from sqlalchemy import Column, Integer, String, Text, DateTime, func
from app.db.base import Base

class Report(Base):  # type: ignore[name-defined]
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=False), server_default=func.now(), nullable=False)

    # Keep nullable to avoid old NOT NULL failures; migration will normalize defaults
    owner_id = Column(Integer, nullable=True)

    name = Column(String(255), nullable=False, server_default="report")
    params_json = Column(Text, nullable=False, server_default="{}")
    filters_json = Column(Text, nullable=False, server_default="{}")

    window_days = Column(Integer, nullable=False, server_default="180")
    business_mode = Column(String(16), nullable=False, server_default="both")
    aggregate_by = Column(String(16), nullable=False, server_default="both")
    time_mode = Column(String(16), nullable=False, server_default="both")

    csv_path = Column(Text, nullable=False, server_default="")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Report id={self.id} name={self.name!r}>"
