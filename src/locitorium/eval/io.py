from __future__ import annotations

import json
from pathlib import Path

from locitorium.models.schema import GoldDoc, PredDoc


def read_jsonl(path: str | Path) -> list[dict]:
    items: list[dict] = []
    with Path(path).open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            items.append(json.loads(line))
    return items


def write_jsonl(path: str | Path, rows: list[dict]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False))
            f.write("\n")


def load_gold(path: str | Path) -> list[GoldDoc]:
    return [GoldDoc.model_validate(item) for item in read_jsonl(path)]


def load_predictions(path: str | Path) -> list[PredDoc]:
    return [PredDoc.model_validate(item) for item in read_jsonl(path)]
