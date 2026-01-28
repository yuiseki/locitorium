import asyncio

import pytest
from tenacity import RetryError

from locitorium.clients.ollama import OllamaClient


class StubAsyncClient:
    def __init__(self, response_json):
        self._response_json = response_json

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, json=None):
        class Resp:
            def __init__(self, payload):
                self._payload = payload

            def raise_for_status(self):
                return None

            def json(self):
                return self._payload

        return Resp(self._response_json)


def test_ollama_generate_parses_json(monkeypatch):
    def stub_client(*args, **kwargs):
        return StubAsyncClient({"message": {"content": "{\"mentions\": []}"}})

    monkeypatch.setattr("httpx.AsyncClient", stub_client)

    client = OllamaClient("https://ollama.yuiseki.net", "llama3.1")
    out = asyncio.run(client.generate("prompt", {"type": "object"}))
    assert out == {"mentions": []}


def test_ollama_generate_invalid_json_raises(monkeypatch):
    def stub_client(*args, **kwargs):
        return StubAsyncClient({"message": {"content": "not-json"}})

    monkeypatch.setattr("httpx.AsyncClient", stub_client)

    client = OllamaClient("https://ollama.yuiseki.net", "llama3.1")
    with pytest.raises(RetryError):
        asyncio.run(client.generate("prompt", {"type": "object"}))
