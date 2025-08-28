from pydantic_settings import BaseSettings
from pydantic import Field, field_validator
from functools import lru_cache
from typing import List, Any

class Settings(BaseSettings):
    app_secret: str = Field(alias="APP_SECRET", default="change-me-please-32bytes")
    sqlite_path: str = Field(default="app.db", alias="SQLITE_PATH")

    # Allow a single string or comma/semicolon separated list in .env (e.g. FRONTEND_ORIGINS=http://localhost:5173,https://acme.com)
    frontend_origins: List[str] = Field(default=["http://localhost:5173"], alias="FRONTEND_ORIGINS")

    bootstrap_admin_email: str = Field(default="admin@example.com", alias="BOOTSTRAP_ADMIN_EMAIL")
    bootstrap_admin_password: str = Field(default="admin123", alias="BOOTSTRAP_ADMIN_PASSWORD")

    jira_base_url: str | None = Field(default=None, alias="JIRA_BASE_URL")
    jira_email: str | None = Field(default=None, alias="JIRA_EMAIL")
    jira_api_token: str | None = Field(default=None, alias="JIRA_API_TOKEN")

    default_window_days: int = Field(default=180, alias="DEFAULT_WINDOW_DAYS")

    business_hours_start: str = Field(default="09:00", alias="BUSINESS_HOURS_START")
    business_hours_end: str = Field(default="17:00", alias="BUSINESS_HOURS_END")
    business_days: str = Field(default="Mon,Tue,Wed,Thu,Fri", alias="BUSINESS_DAYS")
    timezone: str = Field(default="America/New_York", alias="TIMEZONE")

    @field_validator("frontend_origins", mode="before")
    @classmethod
    def _parse_frontend_origins(cls, v: Any):
        # Accept JSON-style list OR simple comma/semicolon separated string
        if isinstance(v, str):
            # If it looks like a JSON list, let pydantic handle it later
            s = v.strip()
            if s.startswith("[") and s.endswith("]"):
                return v
            # Otherwise, split by comma/semicolon
            parts = [p.strip() for p in s.replace(";", ",").split(",") if p.strip()]
            return parts or ["http://localhost:5173"]
        return v

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

@lru_cache
def get_settings() -> Settings:
    return Settings()
