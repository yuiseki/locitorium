from __future__ import annotations

import asyncio
from pathlib import Path

import typer

from locitorium.config import AppConfig
from locitorium.eval.io import load_gold, load_predictions, read_jsonl, write_jsonl
from locitorium.eval.metrics import topk_accuracy
from locitorium.pipeline.runner import run_dataset, run_dataset_stream

app = typer.Typer(add_completion=False)


def _sanitize_model_name(model: str) -> str:
    return model.replace("/", "_").replace(":", "_")


@app.command()
def run(
    input_path: Path = typer.Argument(..., help="Path to dataset.jsonl"),
    output_path: Path = typer.Argument(..., help="Path to predictions.jsonl"),
    model: str | None = typer.Option(None, help="Override Ollama model"),
    thinking: bool | None = typer.Option(
        None, "--thinking/--no-thinking", help="Toggle model thinking if supported"
    ),
    debug_dir: Path | None = typer.Option(None, help="Write raw prompts/responses"),
) -> None:
    config = AppConfig()
    if model or debug_dir or thinking is not None:
        config = AppConfig(
            ollama_model=model or config.ollama_model,
            debug_dir=str(debug_dir) if debug_dir else None,
            ollama_thinking=thinking,
        )
    docs = read_jsonl(input_path)
    asyncio.run(run_dataset_stream(docs, config, str(output_path)))


@app.command()
def bench(
    input_path: Path = typer.Argument(..., help="Path to dataset.jsonl"),
    output_dir: Path = typer.Argument(..., help="Output directory for predictions"),
    models: list[str] = typer.Option(..., help="Ollama models to benchmark"),
    thinking: bool | None = typer.Option(
        None, "--thinking/--no-thinking", help="Toggle model thinking if supported"
    ),
    debug_dir: Path | None = typer.Option(None, help="Write raw prompts/responses"),
) -> None:
    docs = read_jsonl(input_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    for model in models:
        model_debug_dir = None
        if debug_dir:
            model_debug_dir = debug_dir / _sanitize_model_name(model)
        config = AppConfig(
            ollama_model=model,
            debug_dir=str(model_debug_dir) if model_debug_dir else None,
            ollama_thinking=thinking,
        )
        out_path = output_dir / f"predictions_{_sanitize_model_name(model)}.jsonl"
        asyncio.run(run_dataset_stream(docs, config, str(out_path)))
        typer.echo(f"wrote {out_path}")


@app.command()
def eval(
    gold_path: Path = typer.Argument(..., help="Path to dataset.jsonl"),
    pred_path: Path = typer.Argument(..., help="Path to predictions.jsonl"),
    k: int = typer.Option(5, help="k for top-k accuracy"),
) -> None:
    gold = load_gold(gold_path)
    preds = load_predictions(pred_path)
    metrics = topk_accuracy(gold, preds, k)
    for key, value in metrics.items():
        typer.echo(f"{key}: {value}")
