import asyncio

from locitorium.config import AppConfig
from locitorium.pipeline import runner


def test_runner_timeout(monkeypatch):
    async def slow_extract(*args, **kwargs):
        await asyncio.sleep(0.2)
        return ["Japan"]

    monkeypatch.setattr(runner, "extract_mentions", slow_extract)

    config = AppConfig(deadline_s=0.05)
    pred = asyncio.run(runner.run_doc("Text", "d1", config))
    assert pred.results
    assert pred.results[0].status == "timeout"


def test_resolver_fills_missing_results():
    from locitorium.clients.ollama import OllamaClient
    from locitorium.models.schema import Candidate
    from locitorium.pipeline.resolver import resolve_candidates

    class StubClient(OllamaClient):
        async def generate(self, prompt, schema, tag=""):
            return {
                "results": [
                    {
                        "mention_id": "d1:0",
                        "mention": "Minneapolis",
                        "choice": 0,
                        "status": "resolved",
                    }
                ]
            }

    candidates = {
        "d1:0": (
            "Minneapolis",
            [
                Candidate.model_validate(
                    {
                        "rank": 1,
                        "osm_type": "relation",
                        "osm_id": 1,
                        "display_name": "Minneapolis",
                        "lat": "0",
                        "lon": "0",
                        "bbox": ["0", "1", "2", "3"],
                        "country_code": "US",
                        "category": None,
                        "place_rank": None,
                        "importance": None,
                    }
                )
            ],
        ),
        "d1:1": ("Alex Pretti", []),
    }

    client = StubClient("http://example.com", "stub")
    results = asyncio.run(resolve_candidates(client, "text", candidates, tag="t"))
    assert len(results) == 2
