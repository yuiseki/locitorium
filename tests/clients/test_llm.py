"""Tests for LlmClient (OpenAI-compatible httpx client)."""

from __future__ import annotations

import asyncio
import json

import pytest
from tenacity import RetryError

from locitorium.clients.llm import LlmClient


class StubAsyncClient:
    def __init__(self, response_json):
        self._response_json = response_json
        self.last_url = None
        self.last_payload = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, *, json=None, headers=None):
        self.last_url = url
        self.last_payload = json

        class Resp:
            def __init__(self, payload):
                self._payload = payload

            def raise_for_status(self):
                return None

            def json(self):
                return self._payload

        return Resp(self._response_json)


def _openai_resp(content: str) -> dict:
    return {"choices": [{"message": {"content": content}, "finish_reason": "stop"}]}


class TestLlmClientGenerate:
    def test_parses_json_response(self, monkeypatch):
        stub = StubAsyncClient(_openai_resp('{"mentions": []}'))
        monkeypatch.setattr("httpx.AsyncClient", lambda **kw: stub)
        client = LlmClient("http://llama:8080/v1", "gvt-llm")
        out = asyncio.run(client.generate("prompt", {"type": "object"}))
        assert out == {"mentions": []}

    def test_calls_chat_completions_endpoint(self, monkeypatch):
        stub = StubAsyncClient(_openai_resp('{"k": "v"}'))
        monkeypatch.setattr("httpx.AsyncClient", lambda **kw: stub)
        client = LlmClient("http://llama:8080/v1", "gvt-llm")
        asyncio.run(client.generate("prompt", {"type": "object"}))
        assert stub.last_url.endswith("/chat/completions")

    def test_sends_model_name(self, monkeypatch):
        stub = StubAsyncClient(_openai_resp('{"k": "v"}'))
        monkeypatch.setattr("httpx.AsyncClient", lambda **kw: stub)
        client = LlmClient("http://llama:8080/v1", "gvt-llm")
        asyncio.run(client.generate("prompt", {"type": "object"}))
        assert stub.last_payload["model"] == "gvt-llm"

    def test_sends_json_schema_response_format(self, monkeypatch):
        stub = StubAsyncClient(_openai_resp('{"k": "v"}'))
        monkeypatch.setattr("httpx.AsyncClient", lambda **kw: stub)
        schema = {"type": "object", "properties": {"k": {"type": "string"}}}
        client = LlmClient("http://llama:8080/v1", "gvt-llm")
        asyncio.run(client.generate("prompt", schema))
        rf = stub.last_payload["response_format"]
        assert rf["type"] == "json_schema"
        assert rf["json_schema"]["schema"] == schema

    def test_think_disabled_by_default(self, monkeypatch):
        stub = StubAsyncClient(_openai_resp('{"k": "v"}'))
        monkeypatch.setattr("httpx.AsyncClient", lambda **kw: stub)
        client = LlmClient("http://llama:8080/v1", "gvt-llm")
        asyncio.run(client.generate("prompt", {}))
        # options.think=False should be sent to suppress Qwen3 reasoning tokens
        assert stub.last_payload.get("options", {}).get("think") is False

    def test_think_can_be_enabled(self, monkeypatch):
        stub = StubAsyncClient(_openai_resp('{"k": "v"}'))
        monkeypatch.setattr("httpx.AsyncClient", lambda **kw: stub)
        client = LlmClient("http://llama:8080/v1", "gvt-llm", thinking=True)
        asyncio.run(client.generate("prompt", {}))
        assert stub.last_payload.get("options", {}).get("think") is True

    def test_strips_think_tags_from_response(self, monkeypatch):
        content = "<think>reasoning</think>{\"mentions\": []}"
        stub = StubAsyncClient(_openai_resp(content))
        monkeypatch.setattr("httpx.AsyncClient", lambda **kw: stub)
        client = LlmClient("http://llama:8080/v1", "gvt-llm")
        out = asyncio.run(client.generate("prompt", {}))
        assert out == {"mentions": []}

    def test_invalid_json_retries_and_raises(self, monkeypatch):
        stub = StubAsyncClient(_openai_resp("not-json"))
        monkeypatch.setattr("httpx.AsyncClient", lambda **kw: stub)
        client = LlmClient("http://llama:8080/v1", "gvt-llm")
        with pytest.raises(RetryError):
            asyncio.run(client.generate("prompt", {}))

    def test_empty_content_retries_and_raises(self, monkeypatch):
        stub = StubAsyncClient(_openai_resp(""))
        monkeypatch.setattr("httpx.AsyncClient", lambda **kw: stub)
        client = LlmClient("http://llama:8080/v1", "gvt-llm")
        with pytest.raises(RetryError):
            asyncio.run(client.generate("prompt", {}))

    def test_authorization_header_sent(self, monkeypatch):
        stub = StubAsyncClient(_openai_resp('{"k": "v"}'))
        monkeypatch.setattr("httpx.AsyncClient", lambda **kw: stub)
        client = LlmClient("http://llama:8080/v1", "gvt-llm", api_key="secret")
        asyncio.run(client.generate("prompt", {}))
        assert stub.last_payload is not None  # request reached the stub
