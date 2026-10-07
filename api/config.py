"""Settings, from environment variables or .env (see .env.example). Keys are SecretStr: they never print."""

from __future__ import annotations

import logging
import re
from contextvars import ContextVar
from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent

# A run can be forced to mock while the server is live (public uploads without the admin token).
FORCE_MOCK: ContextVar[bool] = ContextVar("force_mock", default=False)

# Model ID -> USD per 1M tokens (input, output). PLACEHOLDERS: fill from the Token Factory pricing page.
PRICES: dict[str, tuple[float, float]] = {
    "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B": (0.06, 0.24),
    "nvidia/nemotron-3-super-120b-a12b": (0.0, 0.0),
    "nvidia/Nemotron-3-Ultra-550b-a55b": (0.0, 0.0),
}
KEYS = ("nebius_api_key", "tavily_api_key", "langsmith_api_key", "admin_token")
LIVE_REQUIRES = ("nebius_api_key", "tavily_api_key")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", env_ignore_empty=True, extra="ignore")

    speccheck_mode: Literal["mock", "live"] = "mock"

    nebius_api_key: SecretStr = SecretStr("")
    nebius_base_url: str = "https://api.tokenfactory.nebius.com/v1/"
    tavily_api_key: SecretStr = SecretStr("")
    langsmith_api_key: SecretStr = SecretStr("")
    admin_token: SecretStr = SecretStr("")

    model_triage: str = "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"
    model_extract: str = "nvidia/nemotron-3-super-120b-a12b"
    model_verify: str = "nvidia/nemotron-3-super-120b-a12b"
    model_write: str = "nvidia/nemotron-3-super-120b-a12b"
    model_reconcile: str = "nvidia/Nemotron-3-Ultra-550b-a55b"
    model_vision: str = ""

    budget_usd_per_run: float = 5.0
    budget_tavily_credits_per_item: float = 25
    budget_tavily_credits_per_day: float = 500
    max_upload_mb: int = 15
    uploads_per_ip_per_hour: int = 10

    # USD per Tavily credit (pay-as-you-go list price).
    tavily_credit_usd: float = 0.008
    # Tavily map is billed per page found, so every map call is capped.
    map_limit: int = 20
    map_max_depth: int = 1
    # Fix step (send-backs only): candidates checked per finding, and the Tavily credit cap per item.
    fix_max_candidates: int = 3
    fix_credit_cap: float = 12
    max_concurrency: int = 4
    # Mock mode only: pause per stage so the UI animation looks like a real run. 0 for eval.
    mock_stage_delay_ms: int = 0

    data_dir: Path = ROOT / "data"
    cases_file: Path = ROOT / "data" / "cases" / "cases.json"
    specs_file: Path = ROOT / "data" / "cases" / "specs.json"
    fixtures_dir: Path = ROOT / "data" / "fixtures"
    raw_dir: Path = ROOT / "data" / "raw"
    cache_dir: Path = ROOT / ".cache"
    runs_dir: Path = ROOT / "runs"
    uploads_dir: Path = ROOT / "data" / "raw" / "uploads"
    scores_file: Path = ROOT / "runs" / "scores.json"
    web_dist: Path = ROOT / "web" / "dist"

    @property
    def mode(self) -> str:
        return self.speccheck_mode

    @property
    def live(self) -> bool:
        """Live calls for the current run: the server is live and this run was not forced to mock."""
        return self.speccheck_mode == "live" and not FORCE_MOCK.get()

    @property
    def models(self) -> dict[str, str]:
        return {r: getattr(self, f"model_{r}") for r in ("triage", "extract", "verify", "write", "reconcile", "vision")}

    @property
    def keys_present(self) -> dict[str, bool]:
        return {k.upper(): bool(getattr(self, k).get_secret_value()) for k in KEYS}

    def secret(self, name: str) -> str:
        return getattr(self, name).get_secret_value()


class MissingKey(RuntimeError):
    pass


def check_startup(s: Settings) -> Settings:
    """Live mode with a missing key stops here, naming the variable. Not a pydantic validator: its errors echo input values."""
    missing = [k.upper() for k in LIVE_REQUIRES if not s.secret(k)]
    if s.speccheck_mode == "live" and missing:
        raise MissingKey(f"SPECCHECK_MODE=live needs {', '.join(missing)} (set it in .env or the environment)")
    return s


settings = check_startup(Settings())


# ---------- log redaction ----------

_PATTERNS = re.compile(r"(Bearer\s+)\S+|\b(sk-|tvly-|lsv2_)[A-Za-z0-9_\-]{8,}")


def redact(text: str) -> str:
    for k in KEYS:
        v = settings.secret(k)
        if len(v) >= 4:
            text = text.replace(v, "***")
    return _PATTERNS.sub(lambda m: (m.group(1) or m.group(2)) + "***", text)


class RedactFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg, record.args = redact(record.getMessage()), None
        return True


def install_redaction() -> None:
    """Redact on every record, whichever logger or handler it goes to (uvicorn's included)."""
    old = logging.getLogRecordFactory()
    if getattr(old, "redacting", False):
        return
    f = RedactFilter()

    def factory(*a, **kw):
        rec = old(*a, **kw)
        f.filter(rec)
        return rec

    factory.redacting = True
    logging.setLogRecordFactory(factory)


install_redaction()
