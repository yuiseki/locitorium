# Locitorium

Text-to-Geospatial service that using Ollama for semantic extracting and Nominatim (OpenStreetMap) for grounding to eliminate hallucinations.

Phase 0 focuses on grounded country-level toponym resolution using a minimal, measurable pipeline.

## Features

- **API Server**: FastAPI-based REST API for location resolution
- **Interactive Web UI**: Playground with real-time map visualization using MapLibre GL JS
- **CLI Tools**: `locitorium resolve` for pipelines (JSONL in, JSONL out),
  `locitorium eval` for batch processing, benchmarking and evaluation
- **LLM Integration**: Ollama-powered semantic extraction
- **OSM Grounding**: Nominatim (OpenStreetMap) for accurate location data
- **Evaluation Metrics**: Top-k accuracy for model comparison

## Quickstart - API Server

Start the development server:

```bash
uv sync
uv run uvicorn locitorium.api.app:app --reload --port 8010
```

Then open http://localhost:8010 in your browser to access the playground.

### API Endpoint

```bash
# Resolve locations from text
curl "http://localhost:8010/api?q=Trump+says+government+will+de-escalate+in+Minnesota"

# Specify model
curl "http://localhost:8010/api?q=Meeting+in+Tokyo&model=granite3.3:2b"
```

See the interactive API documentation at http://localhost:8010#docs

## Quickstart - CLI (pipeline)

`locitorium resolve` is a pipeline stage: JSONL in, JSONL out, one row per
mention. It talks to a running locitorium server (`--server-url`, default
`http://127.0.0.1:30101`), so resolved places can be kept as their own file
and downstream steps rebuilt without re-running resolution.

```bash
echo '{"id":"s1","text":"鎌ヶ谷市の様子です"}' \
  | uv run locitorium resolve > places.jsonl
```

```jsonl
{"input_id": "s1", "chunk_index": 0, "doc_id": "7770…", "mention_id": "7770…:0", "mention": "鎌ヶ谷市", "status": "resolved", "osm_type": "relation", "osm_id": 2679943, "lat": 35.7766455, "lon": 140.0007147, "display_name": "鎌ケ谷市, 千葉県, 日本", "country_code": "JP", "llm_model": "gvt-llm", "error": null}
```

Options:

- `--input` / `--output`: file paths; default stdin/stdout
- `--text-field` / `--id-field`: input field names (default `text` / `id`);
  the identifier is copied to `input_id` on every output row
- `--max-chars` (default 2000) and `--on-too-long error|split|truncate`
  (default `error`): locitorium rejects longer input, and long input also
  degrades LLM output, so oversized records are reported as
  `status=input_too_long` instead of being sent. `split` cuts the text at
  sentence boundaries and resolves each chunk (`chunk_index` tells them apart)
- `--resume out.jsonl`: identifiers already present in that file are copied
  through without calling the server
- `--include-candidates`: keep the Nominatim candidate list in each row
- `--quiet`: no progress on stderr (progress is written to stderr by default)

Every input record produces at least one row. Unresolved mentions keep their
locitorium status (`no_candidate`, `rejected`, `invalid_output`, `timeout`),
and the CLI adds `no_mention`, `missing_text`, `input_too_long` and
`server_error`. The exit code is 1 when any record could not be sent to
locitorium (`missing_text`, `input_too_long`, `server_error`).

```bash
# resolved places only, as CSV
jq -r 'select(.status=="resolved") | [.input_id,.osm_id,.display_name] | @csv' places.jsonl
```

## Quickstart - CLI (evaluation)

Process a dataset:

```bash
uv sync
uv run locitorium eval run data/phase0/dataset.jsonl runs/dev/predictions.jsonl --model gvt-llm
uv run locitorium eval score data/phase0/dataset.jsonl runs/dev/predictions.jsonl
```

Benchmark multiple models:

```bash
uv run locitorium eval bench data/phase0/dataset.jsonl runs/bench \
  --models granite4:3b --models ministral-3:3b --models granite3.3:2b
```

## Configuration

Default settings (configurable via `AppConfig` in `src/locitorium/config.py`):

- **Language**: English
- **Ollama**: https://ollama.yuiseki.net
- **Nominatim**: https://nominatim.yuiseki.net
- **Models** (tested):
  - granite4:3b, ministral-3:3b, granite3.3:2b
  - granite3.2:8b, granite4:1b-h
- **Limits**: 2000 chars input, 20 mentions max, 10 candidates per mention

## Data Format

- **Input + gold**: `data/phase0/dataset.jsonl`
- **Predictions**: `runs/{run_id}/predictions.jsonl`

See `docs/ADR/001.md` for the data contract and evaluation details.

## Development

### Run Tests

```bash
uv run pytest
```

### Project Structure

```
src/locitorium/
├── api/          # FastAPI server + web UI
├── clients/      # Ollama and Nominatim clients
├── eval/         # Metrics and evaluation
├── models/       # Pydantic schemas
├── pipeline/     # Core resolution pipeline
└── prompts/      # LLM prompt templates
```

## Documentation

- [ADR 001](docs/ADR/001.md): Data contract and evaluation
- [ADR 002](docs/ADR/002.md): Architecture decisions
- [PRD](docs/PRD.md): Product requirements
- [Examples](docs/examples.md): Usage examples
