# QuantCore

**Point-in-time, reproducible quantitative equity research infrastructure for US markets.**

QuantCore is a research platform for building historically defensible equity-analysis workflows from canonical market, financial, regulatory, corporate-action, and macroeconomic data. Its deterministic research core covers point-in-time alignment, research datasets, factors, signals, strategies, portfolio construction and analytics, backtesting, performance, attribution, stress analysis, and experiment provenance. A versioned FastAPI product API exposes the research capabilities through explicit contracts.

> **Current status:** The deterministic research core and its product API are substantially implemented. The agentic AI layer, institutional frontend, production cloud deployment, and final scientific evaluation are subsequent phases. The current repository should not be described as an already-completed AI product.

## Why QuantCore exists

Historical equity research is vulnerable to subtle temporal errors: using revised information that was not available at the research date, mixing incompatible observation dates, treating tickers as permanent identities, or allowing research results to depend on mutable inputs. QuantCore is designed around explicit temporal semantics, immutable research identities, deterministic transformations, and auditable provenance.

The central research path is:

```text
External providers
      |
      v
Ingestion -> validation -> normalization -> canonical persistence
                                             |
                                             v
                                  PIT / provenance layer
                                             |
                                             v
                                       Observations
                                             |
                                             v
                                  Research datasets
                                             |
                    +------------------------+------------------------+
                    |                        |                        |
                  Factors                  Signals                Experiments
                    |                        |                        |
                    v                        v                        v
              Factor returns             Strategies              Artifacts
                    |                        |
                    +-----------+------------+
                                |
                                v
                         Portfolio research
                                |
          +---------------------+----------------------+
          |                     |                      |
        Risk                  Stress             Rebalance / costs
          |                     |                      |
          +---------------------+----------------------+
                                |
                                v
                             Backtest
                                |
                    +-----------+-----------+
                    |                       |
               Performance             Attribution
```

## Architectural principles

- **Point-in-time correctness:** price, financial-statement, and corporate-action domains preserve revision information and expose explicit temporal semantics. SEC filing information uses filing dates where available; research calculations operate against an explicit `as_of`.
- **Deterministic research:** canonicalization, ordered identities, validation, and stable fingerprints make research inputs and outputs reproducible.
- **Separation of concerns:** ingestion, processing, persistence, research methodology, product orchestration, and HTTP contracts remain separate boundaries.
- **Explicit research contracts:** factors, signals, strategies, portfolios, backtests, and experiments have versioned identities and validation rules instead of relying on loosely coupled dictionaries.
- **Ownership-aware research resources:** experiment lifecycle and retrieval are scoped to the authenticated resource owner where persistence is involved.
- **Fail-closed API security:** protected research routes require verified OIDC bearer tokens and the required research scope.
- **Provider abstraction:** external data providers are isolated behind provider interfaces/factories so application services do not depend directly on vendor response formats.
- **Operational truth is separated from financial truth:** ingestion health, execution coverage, data quality, provenance, and research validity are distinct concepts.
- **No premature infrastructure:** the current ingestion coordinator is deliberately bounded and synchronous; distributed infrastructure is not introduced until a demonstrated product requirement exists.

## Research capabilities

### Data and temporal foundations

- Security master and issuer/listing identity history
- Historical prices and price-observation revisions
- Financial statements with temporal/filing semantics and revision history
- Corporate actions with revision history
- SEC filings and XBRL fact observations
- Macroeconomic data and vintage-aware semantics
- Ingestion lineage, scheduling, health, quality, retries, idempotency, and stale-run recovery
- Cross-dataset point-in-time reconciliation and alignment

### Quantitative research

- Research observations and canonical metrics
- Historical research datasets and feature-vector fingerprints
- Versioned factor definitions and factor computation
- Cross-sectional factor panels, ranking, and evaluation
- Forward factor returns and factor-return methodology
- Deterministic signals and versioned strategies
- Portfolio construction, risk, factor risk, constraints, rebalancing, transaction costs, and hypothetical stress analysis
- Deterministic backtesting, performance analysis, and portfolio attribution
- Research experiment definitions, runs, results, artifacts, provenance, and comparisons

## Product API

The backend currently exposes **34 router modules and 89 HTTP routes**, including **21 research router modules**. Research endpoints are versioned under `/api/v1/research` except for the legacy research-observation prefix, which is retained by the current implementation.

Research API areas include:

- observations, features, datasets, experiments
- factors, factor panels, factor returns, factor-return methodology, factor evaluations
- signals and strategies
- portfolios, portfolio risk, factor risk, constraints, rebalance, transaction costs, stress
- backtests, backtest performance, and backtest attribution

Protected research endpoints use the `research:read` scope in the current API implementation. The experiment HTTP surface is currently read-oriented; experiment execution remains a service/orchestration concern and is not represented as an invented generic HTTP executor.

See [API documentation](docs/api/README.md).

## Point-in-time and reproducibility

QuantCore treats historical availability as a first-class research constraint. Domain revisions use explicit `known_at` semantics, SEC observations retain filing identity where available, and research services require explicit `as_of` values. Historical datasets and feature vectors expose canonical payloads and deterministic fingerprints; experiment definitions, executions, results, artifacts, and comparisons likewise have canonical identity/fingerprint contracts.

The intended reproducibility chain is:

```text
Research definition
 + PIT dataset identity
 + feature/factor/signal/strategy identities
 + portfolio/backtest configuration
 + execution identity
 + artifact/provenance identity
 = auditable research result
```

See [reproducibility documentation](docs/reproducibility/README.md) and [data-source/temporal documentation](docs/data-sources.md).

## Repository structure

```text
QuantCore/
├── backend/
│   ├── src/quantcore/
│   │   ├── api/             # HTTP application, auth, authorization, routers
│   │   ├── analytics/       # Technical indicator implementations
│   │   ├── core/            # Configuration, enums, exceptions, identity
│   │   ├── db/              # Database/session infrastructure
│   │   ├── ingestion/       # Dataset ingestion and provider adapters
│   │   ├── models/          # SQLAlchemy persistence models
│   │   ├── processing/      # Cleaning, validation, transformation
│   │   ├── repositories/    # Persistence/query boundaries
│   │   ├── schemas/         # Pydantic API contracts
│   │   ├── services/        # Domain and research services
│   │   └── universe/        # Security-universe providers
│   ├── alembic/             # Database migrations
│   ├── tests/               # Unit, service, repository, and API tests
│   ├── pyproject.toml       # Package, runtime, and development dependencies
│   └── uv.lock              # Locked Python dependency graph
├── docs/                    # Public technical and research documentation
├── scripts/                 # Explicit operational/development scripts
├── .env.example             # Environment configuration template
└── LICENSE                  # Project licensing decision/document
```

Future frontend, deployment, and infrastructure directories should be added only when they contain real implementation artifacts; empty placeholder trees are intentionally not treated as product functionality.

## Technology stack

- Python 3.10+
- FastAPI + Uvicorn
- SQLAlchemy 2.x + Alembic
- PostgreSQL / psycopg 3
- Pydantic Settings
- PyJWT + JWKS-based OIDC verification
- pandas
- requests
- uv
- pytest + httpx
- ruff, black, mypy

The current implemented provider adapters cover Yahoo Finance, Financial Modeling Prep, SEC EDGAR, and FRED. The data-source strategy also documents additional providers and future production-feed roles; these should not be described as implemented until their adapters and coverage are actually present. See [Data Sources](docs/data-sources.md) for the current source responsibilities and limitations.

## Development

Requirements: Python 3.10+, PostgreSQL, and `uv`.

```bash
cd backend
uv sync
cp ../.env.example .env
# configure DATABASE_URL, SECRET_KEY, provider keys, and OIDC settings as required
uv run alembic upgrade head
uv run uvicorn quantcore.api.main:app --reload
```

Run the test suite with:

```bash
cd backend
uv run pytest
```

The repository's current validated checkpoint is recorded in the project development history. Test counts are intentionally not hard-coded here because they change as the implementation evolves.

## Documentation

- [Documentation index](docs/README.md)
- [Architecture](docs/architecture/README.md)
- [Research methodology](docs/research/README.md)
- [Point-in-time and data-source semantics](docs/data-sources.md)
- [Reproducibility](docs/reproducibility/README.md)
- [API](docs/api/README.md)
- [Scientific evaluation](docs/scientific/evaluation.md)
- [Publication track](docs/publication/README.md)

## Scientific publication

QuantCore is being documented as a research and engineering system, not merely as a software demo. The publication track will focus on the deterministic, point-in-time, reproducible research framework first. The agentic AI layer will be documented as a later orchestration/reasoning layer over that validated substrate.

The current manuscript is a structured draft. Empirical claims and benchmark results are intentionally marked as pending until the corresponding experiments have been run and archived.

## Roadmap

- [x] Canonical data and provider abstraction
- [x] Ingestion orchestration, health, quality, lineage, and idempotency foundations
- [x] Point-in-time reconciliation and research observation layer
- [x] Research datasets, factors, factor returns, signals, and strategies
- [x] Portfolio construction and portfolio analytics
- [x] Backtesting, performance, attribution, and stress analysis
- [x] Research experiment identity, execution, artifact, provenance, and comparison foundations
- [x] Versioned research product API surface for the implemented analytical capabilities
- [ ] Final product-API architecture review/freeze
- [x] Complete technical documentation and README release
- [ ] Scientific evaluation and reproducibility package
- [ ] Journal submission preparation
- [ ] Agentic AI research layer
- [ ] Institutional research frontend
- [ ] Production deployment, CI/CD, observability, security hardening, and AWS hosting

## Current limitations

QuantCore should not currently be described as a live institutional trading system, execution platform, or completed AI analyst. It does not place orders. Stress analysis is hypothetical and deterministic; it is not a probabilistic risk forecast. Provider coverage and licensing remain production concerns. The current frontend/deployment directories do not represent implemented production applications.

## License

The repository currently contains a `LICENSE` path but its contents are not yet populated in the inspected checkpoint. A final public release must make an explicit licensing decision before publication.
