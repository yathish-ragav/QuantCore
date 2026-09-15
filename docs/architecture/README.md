# Architecture

## System boundary

QuantCore is currently a Python backend organized around canonical financial data, research-domain services, persistence boundaries, and a versioned HTTP API.

```text
                    FastAPI Product API
                schemas + auth + routing
                           |
                           v
                 Research/Product Services
                           |
              +------------+------------+
              |                         |
              v                         v
       Domain/Research Logic       Processing Logic
              |                         |
              v                         v
        Repositories              Provider Adapters
              |                         |
              v                         v
          PostgreSQL             External Data Sources
```

The diagram is conceptual rather than a claim that every service has identical dependencies. Individual service modules have narrower contracts.

## Dependency direction

The intended dependency direction is inward from delivery mechanisms toward domain logic and persistence/provider boundaries:

- API endpoints translate HTTP contracts into service calls and stable responses.
- Services own business rules, orchestration, deterministic validation, and research methodology.
- Repositories own persistence/query behavior.
- SQLAlchemy models represent persisted state.
- Processing components normalize, clean, validate, and transform provider/domain data.
- Provider interfaces/factories isolate external vendor formats from application services.

Pydantic schemas are **API boundary contracts**, not a business-logic layer between ORM models and services.

## Research pipeline

```text
Provider data
   -> ingestion
   -> cleaning / validation / normalization
   -> canonical persistence
   -> revisions / filing identity / provenance
   -> PIT alignment
   -> research observations
   -> historical datasets
   -> features / factors
   -> factor panels / returns / evaluation
   -> signals
   -> strategies
   -> portfolios
   -> risk / constraints / rebalance / transaction costs / stress
   -> backtest
   -> performance / attribution
   -> experiment artifacts and comparisons
```

## Security boundary

Protected research endpoints use OIDC resource-server verification. The current implementation validates bearer tokens against configured issuer, audience, JWKS, and algorithms, then authorizes research reads using the `research:read` scope. Persistent experiment resources use the verified principal's issuer/subject as the ownership identity.

## Error boundary

The API installs handlers for:

- `QuantCoreError` and its domain subclasses;
- FastAPI request validation errors; and
- unhandled exceptions.

Requests receive a propagated or generated `X-Request-ID`, allowing an API response to be correlated with request-level diagnostics.

## Operational boundaries

Ingestion mechanics, scheduling, health, quality, lineage, and stale-run recovery are separate services. The current coordinator is intentionally bounded and synchronous. Distributed queues, caches, streams, or container orchestration are not prerequisites of the current architecture.

## Future product layers

The intended next major layers are:

```text
Deterministic research substrate
            |
            +--> Product API
            |
            +--> Agentic AI research orchestration
            |
            +--> Institutional research workspace
            |
            +--> Production operations / cloud
```

The agentic layer must consume stable research contracts rather than bypassing deterministic research services or generating financial facts independently.
