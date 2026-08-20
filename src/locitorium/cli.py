"""Top-level CLI.

``locitorium resolve`` is the pipeline stage: JSONL on stdin, one row
per mention on stdout, identifiers carried through so that downstream
steps can be rebuilt without re-running resolution. ``--format`` picks
the output shape (``jsonl`` by default).

``locitorium eval ...`` holds the evaluation and benchmarking commands.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import typer

from locitorium.config import AppConfig
from locitorium.eval.cli import app as eval_app
from locitorium.pipeline.output import (
    FORMAT_JSONL,
    OUTPUT_FORMATS,
    STREAMING_FORMATS,
    open_writer,
)
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
        None, "--output", help="Output path (default: stdout)"
    ),
    output_format: str = typer.Option(
        FORMAT_JSONL,
        "--format",
        help="Output format: jsonl (default), json, csv or geojson",
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
        help="Reuse rows for identifiers already present in this JSONL output",
    ),
    timeout_s: float = typer.Option(
        120.0, "--timeout", help="HTTP timeout per request in seconds"
    ),
    quiet: bool = typer.Option(False, "--quiet", help="Suppress progress on stderr"),
) -> None:
    """Resolve place mentions for each JSONL record (JSONL in)."""
    if output_format not in OUTPUT_FORMATS:
        raise typer.BadParameter(
            "must be one of " + ", ".join(OUTPUT_FORMATS), param_hint="--format"
        )
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

    if output_format not in STREAMING_FORMATS:
        # json / geojson are one document each: the closing bracket can
        # only be written once every record has been read, so an
        # interrupted run leaves an incomplete document behind. Progress
        # still goes to stderr, which never mixes into that document.
        progress(
            f"format {output_format} writes a single document; "
            "output is only complete when the run finishes"
        )

    resume_rows = load_resolved_rows(resume_path) if resume_path else None
    records = read_jsonl_stream(input_path)
    out = sys.stdout if output_path is None else output_path.open("w", encoding="utf-8")
    writer = open_writer(output_format, out, include_candidates=include_candidates)

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
            writer.write(row)
        return failures

    try:
        failures = asyncio.run(_run())
        writer.close()
    finally:
        if output_path is not None:
            out.close()

    if failures:
        progress(f"{failures} record(s) could not be sent to locitorium")
        raise typer.Exit(code=1)
