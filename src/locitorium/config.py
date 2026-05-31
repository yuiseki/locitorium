from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class AppConfig:
    # LLM backend — any OpenAI-compatible endpoint (default: k8s llama-server)
    openai_base_url: str = "http://10.108.45.102:8080/v1"
    openai_api_key: str = "dummy"
    openai_model: str = "gvt-llm"
    openai_thinking: bool | None = None  # None → disable (suppress Qwen3 <think>)
    nominatim_base_url: str = "https://nominatim.yuiseki.net"
    debug_dir: str | None = None
    max_chars: int = 2000
    max_mentions: int = 20
    max_candidates_per_mention: int = 10
    nominatim_timeout_s: float = 10.0
    nominatim_limit: int = 10
    nominatim_concurrency: int = 5
    deadline_s: float = 60.0


def config_from_env(**overrides) -> AppConfig:
    """Build AppConfig reading defaults from environment variables.

    Priority: overrides > env vars > AppConfig field defaults.
    Recognized env vars:
      OPENAI_BASE_URL, OPENAI_API_KEY, OPENAI_MODEL
      NOMINATIM_BASE_URL, LOCITORIUM_DEADLINE_S
    """
    defaults = {
        "openai_base_url": os.environ.get("OPENAI_BASE_URL", AppConfig.openai_base_url),
        "openai_api_key":  os.environ.get("OPENAI_API_KEY",  AppConfig.openai_api_key),
        "openai_model":    os.environ.get("OPENAI_MODEL",    AppConfig.openai_model),
        "nominatim_base_url": os.environ.get(
            "NOMINATIM_BASE_URL", AppConfig.nominatim_base_url
        ),
    }
    defaults.update(overrides)
    return AppConfig(**defaults)
