# syntax=docker/dockerfile:1

FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    VIRTUAL_ENV=/app/backend/.venv \
    PATH="/app/backend/.venv/bin:$PATH"

WORKDIR /app/backend

# uv is used only as the locked dependency installer; application processes
# run directly from the created virtual environment.
RUN pip install --no-cache-dir uv

COPY backend/pyproject.toml backend/uv.lock backend/README.md ./
# Install locked third-party dependencies before copying application source so
# dependency layers remain cacheable. The project itself is installed only
# after src/quantcore is present.
RUN uv sync --frozen --no-dev --no-install-project

COPY backend/alembic.ini ./
COPY backend/alembic ./alembic
COPY backend/src ./src

# Install the QuantCore project and its console entry points.
RUN uv sync --frozen --no-dev

RUN useradd --create-home --uid 10001 quantcore \
    && chown -R quantcore:quantcore /app

USER quantcore

EXPOSE 8000

CMD ["uvicorn", "quantcore.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
