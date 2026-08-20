"""JSONL-in / JSONL-out resolution for use as a pipeline stage.

Reads one JSON object per input line, resolves place mentions through a
running locitorium HTTP server (``GET /api?q=...``), and writes one JSON
object per mention. Keeping the resolved places in a file of their own
lets downstream steps be rebuilt without re-running the resolver.
"""

from __future__ import annotations

import json
import sys
from collections.abc import AsyncIterator, Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

DEFAULT_SERVER_URL = "http://127.0.0.1:30101"

# Statuses produced by this module (locitorium itself produces
# resolved / no_candidate / rejected / invalid_output / timeout).
STATUS_NO_MENTION = "no_mention"
STATUS_MISSING_TEXT = "missing_text"
STATUS_INPUT_TOO_LONG = "input_too_long"
STATUS_SERVER_ERROR = "server_error"

# Statuses that mean "the CLI could not even ask locitorium".
FAILURE_STATUSES = frozenset(
    {STATUS_MISSING_TEXT, STATUS_INPUT_TOO_LONG, STATUS_SERVER_ERROR}
)

_SPLIT_MARKS = ("\n", "。", "！", "？", ". ", "! ", "? ", "、", " ")


@dataclass(frozen=True)
class StreamOptions:
    """Field mapping and limits for one streaming run."""

    text_field: str = "text"
    id_field: str = "id"
    max_chars: int = 2000
    on_too_long: str = "error"  # error | split | truncate
    include_candidates: bool = False


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def split_text(text: str, max_chars: int) -> list[str]:
    """Split text into chunks of at most ``max_chars`` characters.

    Prefers sentence-ish boundaries so that each chunk stays readable for
    the LLM; falls back to a hard cut when no boundary is available.
    """
    if max_chars <= 0:
        raise ValueError("max_chars must be positive")
    chunks: list[str] = []
    rest = text
    while len(rest) > max_chars:
        window = rest[:max_chars]
        cut = -1
        for mark in _SPLIT_MARKS:
            idx = window.rfind(mark)
            if idx > cut:
                cut = idx + len(mark)
        if cut <= 0:
            cut = max_chars
        chunk = rest[:cut].strip()
        if chunk:
            chunks.append(chunk)
        rest = rest[cut:]
    rest = rest.strip()
    if rest:
        chunks.append(rest)
    return chunks


def read_jsonl_stream(path: Path | None) -> Iterable[dict[str, Any]]:
    """Yield JSON objects from a file, or from stdin when ``path`` is None."""
    handle = sys.stdin if path is None else path.open("r", encoding="utf-8")
    try:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)
    finally:
        if path is not None:
            handle.close()


def load_resolved_rows(path: Path) -> dict[str, list[dict[str, Any]]]:
    """Group previously written output rows by ``input_id`` for resuming."""
    rows: dict[str, list[dict[str, Any]]] = {}
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            input_id = row.get("input_id")
            if input_id is None:
                continue
            rows.setdefault(str(input_id), []).append(row)
    return rows


def _base_row(input_id: str, chunk_index: int, status: str) -> dict[str, Any]:
    return {
        "input_id": input_id,
        "chunk_index": chunk_index,
        "doc_id": None,
        "mention_id": None,
        "mention": None,
        "status": status,
        "osm_type": None,
        "osm_id": None,
        "lat": None,
        "lon": None,
        "display_name": None,
        "country_code": None,
        "llm_model": None,
        "error": None,
    }


def rows_from_pred(
    input_id: str,
    pred: dict[str, Any],
    chunk_index: int,
    options: StreamOptions,
) -> list[dict[str, Any]]:
    """Flatten one locitorium ``PredDoc`` into one row per mention.

    A document without any mention still produces a row so that no input
    record disappears from the output.
    """
    doc_id = pred.get("doc_id")
    llm_model = (pred.get("model_info") or {}).get("llm_model")
    results = pred.get("results") or []
    if not results:
        row = _base_row(input_id, chunk_index, STATUS_NO_MENTION)
        row["doc_id"] = doc_id
        row["llm_model"] = llm_model
        return [row]

    rows: list[dict[str, Any]] = []
    for result in results:
        row = _base_row(input_id, chunk_index, result.get("status", "invalid_output"))
        row["doc_id"] = doc_id
        row["llm_model"] = llm_model
        row["mention_id"] = result.get("mention_id")
        row["mention"] = result.get("mention")
        selected = result.get("selected") or {}
        if selected:
            row["osm_type"] = selected.get("osm_type")
            row["osm_id"] = selected.get("osm_id")
            row["lat"] = _as_float(selected.get("lat"))
            row["lon"] = _as_float(selected.get("lon"))
            row["display_name"] = selected.get("display_name")
            row["country_code"] = selected.get("country_code")
        if options.include_candidates:
            row["candidates"] = result.get("candidates") or []
        rows.append(row)
    return rows


async def resolve_text(
    client: httpx.AsyncClient,
    server_url: str,
    text: str,
    model: str | None = None,
) -> dict[str, Any]:
    """Call ``GET /api`` on a locitorium server and return the raw PredDoc."""
    params: dict[str, str] = {"q": text}
    if model:
        params["model"] = model
    resp = await client.get(f"{server_url.rstrip('/')}/api", params=params)
    resp.raise_for_status()
    return resp.json()


def _record_id(record: dict[str, Any], options: StreamOptions, line_no: int) -> str:
    value = record.get(options.id_field)
    if value is None or value == "":
        return f"line:{line_no}"
    return str(value)


async def resolve_records(
    records: Iterable[dict[str, Any]],
    options: StreamOptions,
    server_url: str = DEFAULT_SERVER_URL,
    model: str | None = None,
    timeout_s: float = 120.0,
    resume_rows: dict[str, list[dict[str, Any]]] | None = None,
    progress: Callable[[str], None] | None = None,
    client: httpx.AsyncClient | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """Resolve every input record and yield output rows, one per mention.

    Failures are reported as rows with a non-``resolved`` status; nothing
    is silently dropped. Records whose ``input_id`` is present in
    ``resume_rows`` are copied through without touching the server.
    """
    owns_client = client is None
    if client is None:
        client = httpx.AsyncClient(timeout=timeout_s)
    resume_rows = resume_rows or {}
    try:
        for line_no, record in enumerate(records, start=1):
            input_id = _record_id(record, options, line_no)

            cached = resume_rows.get(input_id)
            if cached is not None:
                if progress:
                    progress(f"[{line_no}] {input_id}: reused {len(cached)} row(s)")
                for row in cached:
                    yield row
                continue

            text = record.get(options.text_field)
            if not isinstance(text, str) or not text.strip():
                row = _base_row(input_id, 0, STATUS_MISSING_TEXT)
                row["error"] = f"field {options.text_field!r} missing or empty"
                if progress:
                    progress(f"[{line_no}] {input_id}: missing text")
                yield row
                continue

            text = text.strip()
            chunks: list[str]
            if len(text) <= options.max_chars:
                chunks = [text]
            elif options.on_too_long == "split":
                chunks = split_text(text, options.max_chars)
            elif options.on_too_long == "truncate":
                chunks = [text[: options.max_chars]]
            else:
                row = _base_row(input_id, 0, STATUS_INPUT_TOO_LONG)
                row["error"] = (
                    f"{len(text)} chars exceeds max_chars={options.max_chars}; "
                    "use --on-too-long split or truncate"
                )
                if progress:
                    progress(
                        f"[{line_no}] {input_id}: too long "
                        f"({len(text)} > {options.max_chars})"
                    )
                yield row
                continue

            for chunk_index, chunk in enumerate(chunks):
                try:
                    pred = await resolve_text(client, server_url, chunk, model)
                except Exception as exc:  # network / HTTP / decode failures
                    row = _base_row(input_id, chunk_index, STATUS_SERVER_ERROR)
                    row["error"] = f"{type(exc).__name__}: {exc}"
                    if progress:
                        progress(f"[{line_no}] {input_id}: server error {exc}")
                    yield row
                    continue
                rows = rows_from_pred(input_id, pred, chunk_index, options)
                if progress:
                    statuses = ", ".join(sorted({r["status"] for r in rows}))
                    progress(
                        f"[{line_no}] {input_id} chunk {chunk_index + 1}/"
                        f"{len(chunks)} ({len(chunk)} chars): "
                        f"{len(rows)} row(s) [{statuses}]"
                    )
                for row in rows:
                    yield row
    finally:
        if owns_client:
            await client.aclose()
