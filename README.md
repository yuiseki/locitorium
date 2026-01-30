# Locitorium

Text-to-Geospatial service that using Ollama for semantic extracting and Nominatim (OpenStreetMap) for grounding to eliminate hallucinations.

Phase 0 focuses on grounded country-level toponym resolution using a minimal, measurable pipeline.

## Features

- **API Server**: FastAPI-based REST API for location resolution
- **Interactive Web UI**: Playground with real-time map visualization using MapLibre GL JS
- **CLI Tools**: Batch processing, benchmarking, and evaluation
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
curl "http://localhost:8010/api?q=Meeting+in+Tokyo&model=granite4:3b"
```

See the interactive API documentation at http://localhost:8010#docs

## Quickstart - CLI

Process a dataset:

```bash
uv sync
uv run locitorium run data/phase0/dataset.jsonl runs/dev/predictions.jsonl --model granite4:3b
uv run locitorium eval data/phase0/dataset.jsonl runs/dev/predictions.jsonl
```

Benchmark multiple models:

```bash
uv run locitorium bench data/phase0/dataset.jsonl runs/bench \
  --models granite4:3b --models ministral-3:3b --models granite3.3:2b
```

## Configuration

Default settings (configurable via `AppConfig` in `src/locitorium/config.py`):

- **Language**: English
- **Ollama**: https://ollama.yuiseki.net
- **Nominatim**: https://nominatim.yuiseki.net
- **Models** (tested): granite4:3b, ministral-3:3b, granite3.3:2b
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
