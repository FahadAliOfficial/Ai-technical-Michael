from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True, slots=True)
class Settings:
    model: str = "gpt-4o-mini"
    api_key: str | None = None
    timeout_seconds: float = 30.0
    max_retries: int = 2
    log_path: Path = Path("logs/agent.jsonl")
    catalog_path: Path = Path("data/catalog.json")
    inventory_path: Path = Path("data/inventory.json")
    reviews_path: Path = Path("data/reviews.json")
    tool_manifest_path: Path = Path("data/tool_manifest.json")

    @classmethod
    def from_env(cls, env_file: str | Path | None = ".env") -> "Settings":
        if env_file:
            load_dotenv(env_file, override=False)
        return cls(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            api_key=os.getenv("OPENAI_API_KEY") or None,
            timeout_seconds=float(os.getenv("OPENAI_TIMEOUT_SECONDS", "30")),
            max_retries=int(os.getenv("OPENAI_MAX_RETRIES", "2")),
            log_path=Path(os.getenv("SHOPPING_AGENT_LOG_PATH", "logs/agent.jsonl")),
        )

