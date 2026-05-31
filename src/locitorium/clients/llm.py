"""OpenAI-compatible LLM client using httpx.

Replaces the Ollama-native client. Targets any OpenAI-compatible endpoint,
including llama-server (http://10.108.45.102:8080/v1 on the k8s cluster).

Key differences from the Ollama client:
  - Endpoint: /v1/chat/completions  (not /api/chat)
  - Structured output: response_format.json_schema  (not format: schema)
  - Thinking suppression: options.think=False in body (Qwen3 via llama-server)
  - Authorization: Bearer token via Authorization header
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

_THINK_RE = re.compile(r"<think>[\s\S]*?</think>", re.IGNORECASE)


def _strip_think(text: str) -> str:
    """Remove <think>…</think> blocks emitted by Qwen3 reasoning mode."""
    return _THINK_RE.sub("", text).strip()


def _extract_json(payload: str) -> dict[str, Any]:
    decoder = json.JSONDecoder()
    for idx, ch in enumerate(payload):
        if ch not in "{[":
            continue
        try:
            obj, _ = decoder.raw_decode(payload[idx:])
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            continue
    raise ValueError("No valid JSON object found in response")


def _safe_name(value: str) -> str:
    return value.replace("/", "_").replace(":", "_")


class LlmClient:
    """Async client for OpenAI-compatible /v1/chat/completions endpoints."""

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str = "dummy",
        timeout_s: float = 30.0,
        thinking: bool | None = None,
        debug_dir: Path | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout_s = timeout_s
        # None → default to False (suppress Qwen3 reasoning for structured output)
        self.thinking = thinking if thinking is not None else False
        self.debug_dir = debug_dir

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(min=0.2, max=1.0))
    async def generate(
        self, prompt: str, schema: dict[str, Any], tag: str = ""
    ) -> dict[str, Any]:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "output",
                    "schema": schema,
                    "strict": False,
                },
            },
            # Suppress Qwen3 chain-of-thought tokens so JSON parsing is reliable.
            "options": {"think": self.thinking},
        }

        if self.debug_dir:
            self.debug_dir.mkdir(parents=True, exist_ok=True)
            (self.debug_dir / f"{_safe_name(tag)}_prompt.txt").write_text(
                prompt, encoding="utf-8"
            )

        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        choices = data.get("choices") or []
        message = (choices[0].get("message") or {}) if choices else {}
        raw = message.get("content") or ""

        if self.debug_dir:
            (self.debug_dir / f"{_safe_name(tag)}_response.txt").write_text(
                raw, encoding="utf-8"
            )

        text = _strip_think(raw)
        if not text:
            raise ValueError("Empty LLM response")

        try:
            obj = json.loads(text)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass
        return _extract_json(text)
