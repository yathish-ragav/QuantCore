# QuantCore production container runtime

This directory documents the first production deployment boundary for QuantCore.
The image is intentionally provider-agnostic and does not bundle PostgreSQL.

## Runtime topology

```text
                    Managed PostgreSQL
                           ^
                           |
        +------------------+------------------+
        |                  |                  |
     API service       Worker service    Scheduler service
        |                  |                  |
        +------------------+------------------+
                           |
                    QuantCore database
```

All three processes use the same immutable application image:

- **API** serves the FastAPI product surface.
- **Worker** claims and executes durable ingestion jobs.
- **Scheduler** creates durable ingestion jobs from persistent schedules.

PostgreSQL remains an external managed dependency. The production API exposes
`/health/live` for process liveness and `/health/ready` for database and
production-source readiness.

## Build

From the repository root:

```bash
docker build -f docker/Dockerfile -t quantcore:local .
```

The Dockerfile installs the locked third-party dependencies before copying
application source, then installs the QuantCore project after
`src/quantcore/__init__.py` is present. This keeps dependency layers
cacheable while avoiding an invalid source-tree build.

## Configuration

Do not copy production secrets into the image.

The Compose file requires an explicit production environment file:

```bash
export QUANTCORE_ENV_FILE=/absolute/path/to/quantcore-production.env
```

There is intentionally no default `backend/.env` fallback in the production
Compose file. Local credentials must never be implicitly selected for a
production deployment.

The environment file must provide at least the settings required by
`quantcore.core.config.Settings`, including:

```text
DATABASE_URL=postgresql+psycopg://...
SECRET_KEY=...
ENVIRONMENT=production
MARKET_DATA_PROVIDER=massive
REALTIME_MARKET_DATA_PROVIDER=massive
FINANCIAL_DATA_PROVIDER=sec
REGULATORY_DATA_PROVIDER=sec
MACRO_DATA_PROVIDER=fred
MASSIVE_API_KEY=...
SEC_USER_AGENT=QuantCore/1.0 contact: ...
AUTH_ISSUER=...
AUTH_AUDIENCE=...
AUTH_JWKS_URL=...
AUTH_ALGORITHMS=RS256
```

Production source policy is fail-closed. In particular, production market and
realtime market data must use the configured Massive provider and production
fundamental/regulatory/macro data must use SEC/SEC/FRED respectively.

## Database migrations

Run migrations as an explicit deployment step before promoting the API:

```bash
docker run --rm   --env-file "$QUANTCORE_ENV_FILE"   quantcore:local   alembic upgrade head
```

The migration command is deliberately separate from the API startup process so
multiple API replicas cannot race to perform application migrations.

## Run the three-process stack

```bash
export QUANTCORE_ENV_FILE=/path/to/quantcore-production.env
docker compose -f docker-compose.production.yml up -d --build
```

Verify API liveness:

```bash
curl http://127.0.0.1:8000/health/live
```

Verify readiness:

```bash
curl -i http://127.0.0.1:8000/health/ready
```

A `200` readiness response means the application has validated its production
source policy and can reach PostgreSQL. It does not claim that all market or
financial datasets are complete.

## Operational rules

- Use a managed PostgreSQL service for production persistence and backups.
- Keep API, worker, and scheduler as independently restartable processes.
- Inject secrets through the deployment platform; never bake `.env` files into
  images.
- Run Alembic migrations as a controlled release step.
- Put the API behind TLS and an authenticated edge/load balancer before public
  exposure.
- Scale workers independently from API replicas.
- Do not treat container health as a substitute for ingestion/data-quality
  monitoring.
