# QuantCore Backend

This directory contains the Python backend for QuantCore.

The backend owns the canonical data layer, ingestion/provider abstractions, quantitative research services, persistence/repositories, and the versioned FastAPI product API.

Start with the repository-level [QuantCore README](../README.md), then use the [documentation index](../docs/README.md) for architecture, research methodology, API, reproducibility, evaluation, and publication material.

## Development

```bash
uv sync
uv run alembic upgrade head
uv run uvicorn quantcore.api.main:app --reload
```

Run tests with:

```bash
uv run pytest
```
