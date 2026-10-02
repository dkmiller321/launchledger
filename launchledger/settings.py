"""The only place environment variables are read."""

from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import ValidationError, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ConfigError(SystemExit):
    """Raised at startup when configuration is missing or invalid."""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    llm_mode: Literal["mock", "openrouter"] = "mock"
    openrouter_api_key: str = ""
    workflow_model: str = ""
    router_model: str = ""
    compare_model: str = ""
    systems_base_url: str = "http://127.0.0.1:8000"
    frozen_today: date | None = None
    drift_monitor_interval_s: int = 300
    drift_injection: bool = False
    test_mode: bool = False
    mock_latency_ms: int = 0
    eval_drafts_dir: Path = Path("evals/cases/drafts")
    eval_cases_dir: Path = Path("evals/cases")
    host: str = "127.0.0.1"
    port: int = 8000

    @model_validator(mode="after")
    def _openrouter_needs_key(self) -> "Settings":
        if self.llm_mode == "openrouter":
            missing = [
                name.upper()
                for name in ("openrouter_api_key", "workflow_model", "router_model")
                if not getattr(self, name)
            ]
            if missing:
                raise ValueError(f"LLM_MODE=openrouter requires {', '.join(missing)}")
        return self


def load_settings(env_file: str | None = ".env") -> Settings:
    """Read settings once; turn validation errors into a message naming the variable."""
    try:
        return Settings(_env_file=env_file)
    except ValidationError as exc:
        problems = []
        for err in exc.errors():
            loc = "_".join(str(part) for part in err["loc"]).upper() or "SETTINGS"
            problems.append(f"{loc}: {err['msg']}")
        raise ConfigError("Invalid configuration: " + "; ".join(problems)) from None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return load_settings()
