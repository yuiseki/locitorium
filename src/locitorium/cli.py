"""Top-level CLI.

``locitorium resolve`` is the pipeline stage: JSONL on stdin, JSONL on
stdout, one row per mention, identifiers carried through so that
downstream steps can be rebuilt without re-running resolution.

``locitorium eval ...`` holds the evaluation and benchmarking commands.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import typer

from locitorium.config import AppConfig
from locitorium.eval.cli import app as eval_app
from locitorium.pipeline.stream import (
    DEFAULT_SERVER_URL,
    FAILURE_STATUSES,
    StreamOptions,
    load_resolved_rows,
    read_jsonl_stream,
    resolve_records,
)

app = typer.Typer(add_completion=False, help="Locitorium command line tools.")
app.add_typer(eval_app, name="eval")


@app.command()
def resolve(
    input_path: Path | None = typer.Option(
        None, "--input", help="Input JSONL path (default: stdin)"
    ),
    output_path: Path | None = typer.Option(
        None, "--output", help="Output JSONL path (default: stdout)"
    ),
    text_field: str = typer.Option(
        "text", "--text-field", help="Input field holding the text to resolve"
    ),
    id_field: str = typer.Option(
        "id", "--id-field", help="Input field holding the record identifier"
    ),
    server_url: str = typer.Option(
        DEFAULT_SERVER_URL, "--server-url", help="Locitorium server base URL"
    ),
    model: str | None = typer.Option(None, "--model", help="Override LLM model"),
    max_chars: int = typer.Option(
        AppConfig.max_chars, "--max-chars", help="Per-request input character limit"
    ),
    on_too_long: str = typer.Option(
        "error",
        "--on-too-long",
        help="What to do when text exceeds --max-chars: error, split or truncate",
    ),
    include_candidates: bool = typer.Option(
        False, "--include-candidates", help="Keep the candidate list in each row"
    ),
    resume_path: Path | None = typer.Option(
        None,
        "--resume",
        help="Reuse rows for identifiers already present in this output JSONL",
    ),
    timeout_s: float = typer.Option(
        120.0, "--timeout", help="HTTP timeout per request in seconds"
    ),
    quiet: bool = typer.Option(False, "--quiet", help="Suppress progress on stderr"),
) -> None:
    """Resolve place mentions for each JSONL record (JSONL in, JSONL out)."""
    if on_too_long not in {"error", "split", "truncate"}:
        raise typer.BadParameter(
            "must be error, split or truncate", param_hint="--on-too-long"
        )
    if max_chars <= 0:
        raise typer.BadParameter("must be positive", param_hint="--max-chars")

    options = StreamOptions(
        text_field=text_field,
        id_field=id_field,
        max_chars=max_chars,
        on_too_long=on_too_long,
        include_candidates=include_candidates,
    )

    def progress(message: str) -> None:
        if not quiet:
            print(message, file=sys.stderr, flush=True)

    resume_rows = load_resolved_rows(resume_path) if resume_path else None
    records = read_jsonl_stream(input_path)
    out = sys.stdout if output_path is None else output_path.open("w", encoding="utf-8")

    async def _run() -> int:
        failures = 0
        async for row in resolve_records(
            records,
            options,
            server_url=server_url,
            model=model,
            timeout_s=timeout_s,
            resume_rows=resume_rows,
            progress=progress,
        ):
            if row["status"] in FAILURE_STATUSES:
                failures += 1
            out.write(json.dumps(row, ensure_ascii=False))
            out.write("\n")
            out.flush()
        return failures

    try:
        failures = asyncio.run(_run())
    finally:
        if output_path is not None:
            out.close()

    if failures:
        progress(f"{failures} record(s) could not be sent to locitorium")
        raise typer.Exit(code=1)
