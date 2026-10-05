"""Settings. Everything comes from environment variables (see .env.example)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # dotenv is optional
    pass

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    mode: str = os.getenv("SPECCHECK_MODE", "mock")  # "mock" or "live"

    nebius_api_key: str = os.getenv("NEBIUS_API_KEY", "")
    nebius_base_url: str = os.getenv("NEBIUS_BASE_URL", "https://api.tokenfactory.nebius.com/v1/")
    tavily_api_key: str = os.getenv("TAVILY_API_KEY", "")

    models: dict[str, str] = field(
        default_factory=lambda: {
            "nano": os.getenv("MODEL_NANO", "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"),
            "omni": os.getenv("MODEL_OMNI", "nvidia/Nemotron-3-Nano-Omni"),
            "super": os.getenv("MODEL_SUPER", "nvidia/Nemotron-3-Super-120B-A12B"),
            "ultra": os.getenv("MODEL_ULTRA", "nvidia/Nemotron-3-Ultra"),
        }
    )

    # USD per 1M tokens (input, output). PLACEHOLDERS: replace with Token Factory prices before reporting cost.
    prices: dict[str, tuple[float, float]] = field(
        default_factory=lambda: {
            "nano": (0.06, 0.24),
            "omni": (0.06, 0.24),
            "super": (0.0, 0.0),
            "ultra": (0.0, 0.0),
        }
    )
    # USD per Tavily credit (pay-as-you-go list price).
    tavily_credit_usd: float = 0.008

    max_concurrency: int = int(os.getenv("MAX_CONCURRENCY", "4"))
    # Mock mode only: pause per stage so the UI animation looks like a real run. 0 for eval.
    mock_stage_delay_ms: int = int(os.getenv("MOCK_STAGE_DELAY_MS", "0"))

    data_dir: Path = ROOT / "data"
    cases_file: Path = ROOT / "data" / "cases" / "cases.json"
    specs_file: Path = ROOT / "data" / "cases" / "specs.json"
    fixtures_dir: Path = ROOT / "data" / "fixtures"
    raw_dir: Path = ROOT / "data" / "raw"
    cache_dir: Path = ROOT / ".cache"
    runs_dir: Path = ROOT / "runs"
    web_dist: Path = ROOT / "web" / "dist"

    @property
    def live(self) -> bool:
        return self.mode == "live"


settings = Settings()
