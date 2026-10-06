# QuantCore production container runtime

This directory documents the first production deployment boundary for QuantCore.
The image is intentionally provider-agnostic and does not bundle PostgreSQL.

## Local development

Use the root `docker-compose.yml` with `.env.docker` for a self-contained local
stack. It runs PostgreSQL in a named persistent volume and runs migrations,
bootstrap, API, worker, and scheduler in dependency order. The app containers
use the Compose network; host-side scripts can connect through loopback port
5433 by using the `DATABASE_URL` in `.env.docker`.

Run the repository helper from any directory (using its absolute path if needed):

```bash
/path/to/QuantCore/scripts/quantcore-local up
/path/to/QuantCore/scripts/quantcore-local ps
/path/to/QuantCore/scripts/quantcore-local restart
/path/to/QuantCore/scripts/quantcore-local health
```

On first use, the helper creates `.env.docker` from the local template, generates
a local `SECRET_KEY`, and sets owner-only permissions. It never overwrites an
existing environment file. Its absolute Compose paths avoid dependence on the
current working directory. Use `scripts/quantcore-local logs [service]` to inspect logs,
`scripts/quantcore-local restart` to restart the database and long-running
services without deleting data, and `scripts/quantcore-local down` to stop the
stack while preserving the PostgreSQL volume. The helper intentionally does not offer a volume-deletion
option. Local credentials are not suitable for production.

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

The SQLAlchemy pool is process-local. With the Compose defaults (two API
workers, one ingestion worker, and one scheduler), `DB_POOL_SIZE=5` and
`DB_MAX_OVERFLOW=5` permit up to 40 application connections in aggregate
(4 processes × 10 connections). This is a ceiling, not expected steady-state
usage. Reserve PostgreSQL connections for administration, migrations, and
other applications; set lower values if the database connection limit requires
it. Increase them only after measuring concurrency and confirming the database
capacity.

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
DB_POOL_SIZE=5
DB_MAX_OVERFLOW=5
DB_POOL_RECYCLE_SECONDS=1800
LOG_LEVEL=INFO
LOG_FORMAT=json
```

Production source policy is fail-closed. In particular, production market and
realtime market data must use the configured Massive provider and production
fundamental/regulatory/macro data must use SEC/SEC/FRED respectively.

### Operational logging

Production processes emit one JSON object per application log event to stdout.
The default `LOG_FORMAT=json` is intended for CloudWatch or another centralized
log collector; local development may set `LOG_FORMAT=text` for readability.
The API records request method, path, status, request ID, and duration. Ingestion
worker logs include job, worker, dataset, attempt, result counts, and duration.
Logs must never contain provider API keys, database credentials, or raw request
bodies.

## Database migrations

Run migrations as an explicit deployment step before starting or promoting
application services. Build the same immutable image used by the stack, then run
the one-shot migration service:

```bash
docker compose -f docker-compose.production.yml build
docker compose -f docker-compose.production.yml run --rm migrate
```

Only after the migration exits successfully, start the bootstrap and long-running
services:

```bash
docker compose -f docker-compose.production.yml up -d bootstrap api worker scheduler
```

The `migrate` service is intentionally not an automatic dependency of bootstrap.
This keeps schema changes an explicit release action and prevents an ordinary
service restart from implicitly applying database migrations. The operator must
not start or promote application services if the migration command fails.

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
- Run Alembic migrations as a controlled release step before starting or
  promoting application services; do not rely on an ordinary `up` to migrate.
- Put the API behind TLS and an authenticated edge/load balancer before public
  exposure.
- Scale workers independently from API replicas.
- Do not treat container health as a substitute for ingestion/data-quality
  monitoring.

## Declarative ingestion schedules

The scheduler is intentionally passive: it only creates durable jobs from
rows already present in `ingestion_schedules`. Production deployments can
bootstrap those rows from `QUANTCORE_INGESTION_SCHEDULES_JSON`.

The variable is a JSON array. Each entry requires `name`, `dataset`, and
`interval_seconds`; `symbols`, `limit`, `only_stale`, `enabled`, and a timezone-aware
`next_run_at` are optional. For an unbounded schedule, omit `symbols` and `limit`;
the scheduler snapshots the current active security universe and shards it into
bounded jobs.

Example:

```text
QUANTCORE_INGESTION_SCHEDULES_JSON=[{"name":"daily-price-history","dataset":"price_history","interval_seconds":86400,"only_stale":true,"enabled":true}]
```

The production Compose stack runs a one-shot `bootstrap` service after
migrations and before the worker/scheduler. Existing schedules are left alone
when their declared configuration matches. Configuration drift fails the
bootstrap rather than silently mutating a live schedule.

Keep the variable as `[]` until a production cadence has been deliberately
selected and capacity-tested.
