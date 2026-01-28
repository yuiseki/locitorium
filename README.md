# locitorium

Text-to-Geospatial service that using Ollama for semantic extracting and Nominatim (OpenStreetMap) for grounding to eliminate hallucinations.

Phase 0 focuses on grounded country-level toponym resolution using a minimal, measurable pipeline.

## Quickstart (Phase 0)

```bash
uv sync
uv run locitorium run data/phase0/dataset.jsonl runs/dev/predictions.jsonl --model granite4:3b
uv run locitorium eval data/phase0/dataset.jsonl runs/dev/predictions.jsonl
```

## Phase 0 defaults

- Language: English
- Ollama: https://ollama.yuiseki.net
- Nominatim: https://nominatim.yuiseki.net
- Recommended models (tested): granite4:3b, ministral-3:3b, granite3.3:2b

## Benchmark multiple models

```bash
uv run locitorium bench data/phase0/dataset.jsonl runs/bench \\
  --models granite4:3b --models ministral-3:3b --models granite3.3:2b
```

## Data

Input + gold: `data/phase0/dataset.jsonl`
Predictions: `runs/{run_id}/predictions.jsonl`

See `docs/ADR/001.md` for the data contract and evaluation details.
