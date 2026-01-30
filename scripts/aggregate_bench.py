#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

from locitorium.eval.io import load_gold, load_predictions
from locitorium.eval.metrics import topk_accuracy


def _safe_model_to_filename(model: str) -> str:
    return model.replace("/", "_").replace(":", "_")


def _iter_models(models_path: Path | None, preds_dir: Path) -> Iterable[str]:
    if models_path and models_path.exists():
        for line in models_path.read_text(encoding="utf-8").splitlines():
            model = line.strip()
            if model:
                yield model
        return
    for path in sorted(preds_dir.glob("predictions_*.jsonl")):
        yield path.stem.replace("predictions_", "")


def _avg(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Aggregate top1/top5 and timing metrics for predictions."
    )
    parser.add_argument(
        "--gold",
        required=True,
        help="Path to gold dataset.jsonl (e.g., tmp/phase0_10.jsonl)",
    )
    parser.add_argument(
        "--preds-dir",
        required=True,
        help="Directory containing predictions_*.jsonl",
    )
    parser.add_argument(
        "--models",
        help="Optional models.txt to define order",
    )
    parser.add_argument(
        "--k",
        type=int,
        default=5,
        help="k for top-k accuracy (default: 5)",
    )
    args = parser.parse_args()

    gold_path = Path(args.gold)
    preds_dir = Path(args.preds_dir)
    models_path = Path(args.models) if args.models else None

    rows: list[list[str]] = []
    gold = load_gold(gold_path)
    for model in _iter_models(models_path, preds_dir):
        pred_path = preds_dir / f"predictions_{_safe_model_to_filename(model)}.jsonl"
        if not pred_path.exists() or pred_path.stat().st_size == 0:
            continue

        preds = load_predictions(pred_path)
        metrics = topk_accuracy(gold, preds, args.k)

        totals = []
        extracts = []
        candidates = []
        resolves = []
        for doc in preds:
            m = getattr(doc, "metrics", None)
            if not m:
                continue
            totals.append(m.total_s)
            if m.extract_s is not None:
                extracts.append(m.extract_s)
            if m.candidate_s is not None:
                candidates.append(m.candidate_s)
            if m.resolve_s is not None:
                resolves.append(m.resolve_s)

        rows.append(
            [
                model,
                f"{metrics['top1']:.3f}",
                f"{metrics['topk']:.3f}",
                f"{_avg(totals):.3f}",
                f"{_avg(extracts):.3f}",
                f"{_avg(candidates):.3f}",
                f"{_avg(resolves):.3f}",
                str(len(preds)),
            ]
        )

    header = [
        "model",
        "top1",
        f"top{args.k}",
        "avg_total_s",
        "avg_extract_s",
        "avg_candidate_s",
        "avg_resolve_s",
        "docs",
    ]

    print("| " + " | ".join(header) + " |")
    print("| " + " | ".join("---" for _ in header) + " |")
    for row in rows:
        print("| " + " | ".join(row) + " |")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
