from __future__ import annotations

import asyncio
import hashlib
import json
import time
from typing import Any

from locitorium.clients.nominatim import NominatimClient, NominatimServerError
from pathlib import Path

from locitorium.clients.ollama import OllamaClient
from locitorium.config import AppConfig
from locitorium.models.schema import ModelInfo, PredDoc, PredMetrics, PredResult
from locitorium.pipeline.candidates import generate_candidates
from locitorium.pipeline.extractor import extract_mentions
from locitorium.pipeline.resolver import resolve_candidates


def _config_hash(config: AppConfig) -> str:
    payload = json.dumps(config.__dict__, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]


def _mention_ids(doc_id: str, mentions: list[str]) -> list[tuple[str, str]]:
    return [(f"{doc_id}:{i}", mention) for i, mention in enumerate(mentions)]


def _single_status(doc_id: str, status: str) -> list[PredResult]:
    return [
        PredResult(
            mention_id=f"{doc_id}:{status}",
            mention="",
            status=status,
            selected=None,
            candidates=[],
        )
    ]


async def run_doc(text: str, doc_id: str, config: AppConfig) -> PredDoc:
    if len(text) > config.max_chars:
        raise ValueError("input too long")

    debug_dir = Path(config.debug_dir) if config.debug_dir else None
    ollama = OllamaClient(
        config.ollama_base_url,
        config.ollama_model,
        thinking=config.ollama_thinking,
        debug_dir=debug_dir,
    )
    nominatim = NominatimClient(
        config.nominatim_base_url,
        timeout_s=config.nominatim_timeout_s,
        limit=config.nominatim_limit,
    )

    extract_s: float | None = None
    candidate_s: float | None = None
    resolve_s: float | None = None

    async def _run_pipeline() -> list[PredResult]:
        nonlocal extract_s, candidate_s, resolve_s
        t0 = time.perf_counter()
        mentions = await extract_mentions(
            ollama, text, config.max_mentions, tag=f"{doc_id}_extract"
        )
        extract_s = time.perf_counter() - t0
        mention_pairs = _mention_ids(doc_id, mentions)
        if not mention_pairs:
            candidate_s = 0.0
            resolve_s = 0.0
            return []
        t1 = time.perf_counter()
        candidates = await generate_candidates(
            nominatim,
            mention_pairs,
            concurrency=config.nominatim_concurrency,
            max_candidates=config.max_candidates_per_mention,
        )
        candidate_s = time.perf_counter() - t1
        t2 = time.perf_counter()
        results = await resolve_candidates(
            ollama, text, candidates, tag=f"{doc_id}_resolve"
        )
        resolve_s = time.perf_counter() - t2
        return results

    start_total = time.perf_counter()
    try:
        results = await asyncio.wait_for(_run_pipeline(), timeout=config.deadline_s)
    except asyncio.TimeoutError:
        results = _single_status(doc_id, "timeout")
    except NominatimServerError:
        raise
    except Exception:
        results = _single_status(doc_id, "invalid_output")
    total_s = time.perf_counter() - start_total

    return PredDoc(
        doc_id=doc_id,
        model_info=ModelInfo(
            ollama_model=config.ollama_model,
            ollama_base_url=config.ollama_base_url,
            nominatim_base_url=config.nominatim_base_url,
            config_hash=_config_hash(config),
        ),
        results=results,
        metrics=PredMetrics(
            total_s=total_s,
            extract_s=extract_s,
            candidate_s=candidate_s,
            resolve_s=resolve_s,
        ),
    )


async def run_dataset(docs: list[dict[str, Any]], config: AppConfig) -> list[PredDoc]:
    nominatim = NominatimClient(
        config.nominatim_base_url,
        timeout_s=config.nominatim_timeout_s,
        limit=config.nominatim_limit,
    )
    await nominatim.search("Tokyo")
    outputs: list[PredDoc] = []
    for doc in docs:
        outputs.append(await run_doc(doc["text"], doc["doc_id"], config))
    return outputs


async def run_dataset_stream(
    docs: list[dict[str, Any]],
    config: AppConfig,
    output_path: str,
) -> None:
    nominatim = NominatimClient(
        config.nominatim_base_url,
        timeout_s=config.nominatim_timeout_s,
        limit=config.nominatim_limit,
    )
    await nominatim.search("Tokyo")
    with open(output_path, "w", encoding="utf-8") as f:
        for doc in docs:
            pred = await run_doc(doc["text"], doc["doc_id"], config)
            f.write(pred.model_dump_json())
            f.write("\n")
            f.flush()
