from pydantic_settings import BaseSettings
from pydantic import Field, field_validator
from typing import List, Union
from pathlib import Path
from dotenv import load_dotenv
import json, os

# Resolve project root (parent of app/)
PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = PROJECT_ROOT / ".env"

# Explicitly load .env into process env before Pydantic reads it
load_dotenv(ENV_PATH, override=False)

class Settings(BaseSettings):
    app_secret: str = Field(alias="APP_SECRET")
    sqlite_path: str = Field(alias="SQLITE_PATH", default="app.db")
    frontend_origins: Union[str, List[str]] = Field(alias="FRONTEND_ORIGINS", default="[]")

    bootstrap_admin_email: str = Field(alias="BOOTSTRAP_ADMIN_EMAIL")
    bootstrap_admin_password: str = Field(alias="BOOTSTRAP_ADMIN_PASSWORD")

    jira_base_url: str = Field(alias="JIRA_BASE_URL")
    jira_email: str = Field(alias="JIRA_EMAIL")
    jira_api_token: str = Field(alias="JIRA_API_TOKEN", default="")

    default_window_days: int = Field(alias="DEFAULT_WINDOW_DAYS", default=180)
    business_hours_start: str = Field(alias="BUSINESS_HOURS_START", default="09:00")
    business_hours_end: str = Field(alias="BUSINESS_HOURS_END", default="17:00")
    business_days: str = Field(alias="BUSINESS_DAYS", default="Mon,Tue,Wed,Thu,Fri")
    timezone: str = Field(alias="TIMEZONE", default="America/New_York")

    @field_validator("frontend_origins")
    @classmethod
    def parse_frontend_origins(cls, v):
        if isinstance(v, list):
            return v
        s = str(v).strip()
        if not s:
            return []
        try:
            data = json.loads(s)
            if isinstance(data, list):
                return data
        except Exception:
            pass
        return [p.strip() for p in s.replace(";", ",").split(",") if p.strip()]

    class Config:
        env_file = str(ENV_PATH)  # Always use repo-root .env
        env_file_encoding = "utf-8"

settings = Settings()

# Startup hint (no secrets)
if os.getenv("PRINT_SETTINGS_ON_STARTUP", "1") == "1":
    try:
        print(f"[settings] env_file={ENV_PATH} exists={ENV_PATH.exists()} env_token_present={bool(os.getenv('JIRA_API_TOKEN'))} settings_token_present={bool(settings.jira_api_token)}")
    except Exception:
        pass
