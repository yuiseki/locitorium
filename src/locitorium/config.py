from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AppConfig:
    ollama_base_url: str = "https://ollama.yuiseki.net"
    nominatim_base_url: str = "https://nominatim.yuiseki.net"
    ollama_model: str = "lfm2.5-thinking:1.2b"
    ollama_thinking: bool | None = None
    debug_dir: str | None = None
    max_chars: int = 2000
    max_mentions: int = 20
    max_candidates_per_mention: int = 10
    nominatim_timeout_s: float = 10.0
    nominatim_limit: int = 10
    nominatim_concurrency: int = 5
    deadline_s: float = 60.0
