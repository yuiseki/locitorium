from __future__ import annotations

import asyncio

from locitorium.clients.nominatim import NominatimClient
from locitorium.models.schema import Candidate


async def generate_candidates(
    client: NominatimClient,
    mentions: list[tuple[str, str]],
    concurrency: int,
    max_candidates: int,
) -> dict[str, tuple[str, list[Candidate]]]:
    sem = asyncio.Semaphore(concurrency)

    async def _one(mention_id: str, mention: str) -> tuple[str, tuple[str, list[Candidate]]]:
        async with sem:
            items = await client.search(mention)
            return mention_id, (mention, items[:max_candidates])

    tasks = [_one(mid, m) for mid, m in mentions]
    results = await asyncio.gather(*tasks, return_exceptions=False)
    return {mention_id: payload for mention_id, payload in results}
