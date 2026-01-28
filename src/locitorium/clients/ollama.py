from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential


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
    raise ValueError("Invalid JSON response")


def _safe_name(value: str) -> str:
    return value.replace("/", "_").replace(":", "_")


class OllamaClient:
    def __init__(
        self,
        base_url: str,
        model: str,
        timeout_s: float = 30.0,
        thinking: bool | None = None,
        debug_dir: Path | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_s = timeout_s
        self.thinking = thinking
        self.debug_dir = debug_dir

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(min=0.2, max=1.0))
    async def generate(
        self, prompt: str, schema: dict[str, Any], tag: str = ""
    ) -> dict[str, Any]:
        url = f"{self.base_url}/api/chat"
        options: dict[str, Any] = {"temperature": 0}
        if self.thinking is not None:
            options["thinking"] = self.thinking

        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "format": schema,
            "options": options,
        }
        if self.debug_dir:
            self.debug_dir.mkdir(parents=True, exist_ok=True)
            prompt_path = self.debug_dir / f"{_safe_name(tag)}_prompt.txt"
            prompt_path.write_text(prompt, encoding="utf-8")
        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()

        message = data.get("message", {}) or {}
        response_text = message.get("content", "")
        if self.debug_dir:
            response_path = self.debug_dir / f"{_safe_name(tag)}_response.txt"
            response_path.write_text(response_text, encoding="utf-8")
        if not response_text:
            raise ValueError("Empty Ollama response")
        try:
            obj = json.loads(response_text)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass
        return _extract_json(response_text)
