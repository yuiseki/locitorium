import asyncio

from locitorium.clients.nominatim import NominatimClient


class StubAsyncClient:
    def __init__(self, response_json, capture):
        self._response_json = response_json
        self._capture = capture

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url, params=None):
        self._capture["url"] = url
        self._capture["params"] = params

        class Resp:
            def __init__(self, payload):
                self._payload = payload
                self.status_code = 200

            def raise_for_status(self):
                return None

            def json(self):
                return self._payload

        return Resp(self._response_json)


def test_nominatim_search_params(monkeypatch):
    capture = {}
    response = [
        {
            "osm_type": "relation",
            "osm_id": 1,
            "display_name": "Japan",
            "lat": "35",
            "lon": "139",
            "boundingbox": ["0", "1", "2", "3"],
            "address": {"country_code": "jp"},
        }
    ]

    def stub_client(*args, **kwargs):
        return StubAsyncClient(response, capture)

    monkeypatch.setattr("httpx.AsyncClient", stub_client)

    client = NominatimClient("https://nominatim.yuiseki.net", limit=5)
    results = asyncio.run(client.search("Japan"))

    assert capture["url"] == "https://nominatim.yuiseki.net/search"
    assert capture["params"]["q"] == "Japan"
    assert capture["params"]["format"] == "jsonv2"
    assert capture["params"]["addressdetails"] == 1
    assert capture["params"]["limit"] == 5
    assert results[0].country_code == "JP"
