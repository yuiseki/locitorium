from __future__ import annotations

from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from locitorium.models.schema import Candidate


class NominatimServerError(RuntimeError):
    pass


class NominatimClient:
    def __init__(self, base_url: str, timeout_s: float = 10.0, limit: int = 10) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s
        self.limit = limit

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=0.2, max=1.0))
    async def search(self, query: str) -> list[Candidate]:
        url = f"{self.base_url}/search"
        params = {
            "q": query,
            "format": "jsonv2",
            "addressdetails": 1,
            "limit": self.limit,
        }
        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            resp = await client.get(url, params=params)
            if resp.status_code >= 500:
                raise NominatimServerError(
                    f"Nominatim server error: {resp.status_code}"
                )
            resp.raise_for_status()
            data = resp.json()

        candidates: list[Candidate] = []
        for idx, item in enumerate(data, start=1):
            address = item.get("address", {}) or {}
            candidates.append(
                Candidate(
                    rank=idx,
                    osm_type=item.get("osm_type", ""),
                    osm_id=item.get("osm_id", ""),
                    display_name=item.get("display_name", ""),
                    lat=item.get("lat", ""),
                    lon=item.get("lon", ""),
                    bbox=item.get("boundingbox", []) or [],
                    country_code=address.get("country_code"),
                    category=item.get("category"),
                    place_rank=item.get("place_rank"),
                    importance=item.get("importance"),
                )
            )
        return candidates
