from __future__ import annotations

from locitorium.clients.ollama import OllamaClient
from locitorium.models.schema import Candidate, PredResult, SelectedCandidate
from locitorium.prompts.resolve import ResolveOutput, build_prompt


def _candidates_payload(
    candidates_by_id: dict[str, tuple[str, list[Candidate]]]
) -> list[dict]:
    payload = []
    for mention_id, (mention, candidates) in candidates_by_id.items():
        payload.append(
            {
                "mention_id": mention_id,
                "mention": mention,
                "candidates": [
                    {
                        "index": idx,
                        "display_name": c.display_name,
                        "country_code": c.country_code,
                        "osm_type": c.osm_type,
                        "osm_id": c.osm_id,
                    }
                    for idx, c in enumerate(candidates)
                ],
            }
        )
    return payload


def _default_results(
    candidates_by_id: dict[str, tuple[str, list[Candidate]]]
) -> list[PredResult]:
    results = []
    for mention_id, (mention, candidates) in candidates_by_id.items():
        status = "no_candidate" if not candidates else "rejected"
        results.append(
            PredResult(
                mention_id=mention_id,
                mention=mention,
                status=status,
                selected=None,
                candidates=candidates,
            )
        )
    return results


async def resolve_candidates(
    client: OllamaClient,
    text: str,
    candidates_by_id: dict[str, tuple[str, list[Candidate]]],
    tag: str,
) -> list[PredResult]:
    if not candidates_by_id:
        return []

    if all(len(cands) == 0 for _, cands in candidates_by_id.values()):
        return _default_results(candidates_by_id)

    payload = _candidates_payload(candidates_by_id)
    prompt = build_prompt(text, payload)
    schema = ResolveOutput.model_json_schema()
    data = await client.generate(prompt=prompt, schema=schema, tag=tag)
    parsed = ResolveOutput.model_validate(data)

    results: list[PredResult] = []
    by_id = {mid: (mention, cands) for mid, (mention, cands) in candidates_by_id.items()}
    seen_ids: set[str] = set()

    for item in parsed.results:
        mention_id = item.mention_id
        seen_ids.add(mention_id)
        mention, candidates = by_id.get(mention_id, (item.mention, []))
        selected = None
        status = item.status
        if item.choice >= 0 and item.choice < len(candidates):
            cand = candidates[item.choice]
            selected = SelectedCandidate(
                osm_type=cand.osm_type,
                osm_id=cand.osm_id,
                lat=cand.lat,
                lon=cand.lon,
                bbox=cand.bbox,
                display_name=cand.display_name,
                country_code=cand.country_code,
                confidence=None,
            )
            status = "resolved"
        elif not candidates:
            status = "no_candidate"
        else:
            status = "rejected"

        results.append(
            PredResult(
                mention_id=mention_id,
                mention=mention,
                status=status,
                selected=selected,
                candidates=candidates,
            )
        )

    missing_ids = set(by_id.keys()) - seen_ids
    for mention_id in missing_ids:
        mention, candidates = by_id[mention_id]
        status = "no_candidate" if not candidates else "rejected"
        results.append(
            PredResult(
                mention_id=mention_id,
                mention=mention,
                status=status,
                selected=None,
                candidates=candidates,
            )
        )

    return results
