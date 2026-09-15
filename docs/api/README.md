# API

## Base

The current application is a FastAPI service. Research endpoints are generally versioned under:

```text
/api/v1/research
```

The research-observation endpoint retains the existing `/research-observations` prefix in the current implementation.

## Authentication

Protected research endpoints require a bearer access token. The authentication layer is a generic OIDC resource-server implementation using:

- configured issuer;
- configured audience;
- configured JWKS URL;
- configured signing algorithms (RS256 by default); and
- required token claims including `exp`, `sub`, `iss`, and `aud`.

Authentication fails closed when the OIDC configuration is incomplete.

## Authorization

Current research analytical routes require:

```text
research:read
```

The authenticated principal's issuer and subject are also used to construct a stable `ResourceOwner` for owner-scoped research resources.

## Research endpoint groups

| Group | Purpose |
|---|---|
| Observations | Read materialized research observations |
| Features | Read feature vectors |
| Datasets | Build/read historical research datasets |
| Experiments | Read runs, results, artifacts, provenance, comparisons |
| Factors | Retrieve factor definitions/values |
| Factor panels | Build cross-sectional factor panels |
| Factor returns | Compute forward factor returns |
| Factor return methodology | Compute bucketed factor-return series |
| Factor evaluations | Evaluate ranked factor panels |
| Signals | Construct deterministic research signals |
| Strategies | Validate strategy definitions |
| Portfolios | Construct target portfolios |
| Portfolio risk | Analyze concentration/risk snapshots |
| Portfolio factor risk | Analyze factor exposures/risk |
| Portfolio constraints | Validate constraint definitions |
| Portfolio rebalance | Analyze target/current portfolio transitions |
| Portfolio transaction costs | Calculate transaction-cost impacts |
| Portfolio stress | Apply deterministic hypothetical shocks |
| Backtests | Run historical portfolio backtests |
| Backtest performance | Analyze backtest performance |
| Backtest attribution | Attribute portfolio/backtest results |

## Contract policy

API endpoints should remain thin. They should:

1. validate/deserialize the HTTP request;
2. enforce authentication/authorization and bounded request limits;
3. translate request data into domain/service contracts;
4. invoke the appropriate service;
5. translate the result into the stable response schema.

Research methodology must remain in services, not in route handlers.

## Error contract

The application registers centralized handlers for domain errors, request validation errors, and unexpected exceptions. API consumers should use the structured error response rather than depend on Python exception text.

## Experiment execution boundary

The current HTTP experiment API is read-oriented. The service layer contains lifecycle/execution machinery, but a generic HTTP execution endpoint has deliberately not been invented. A future asynchronous/agentic orchestration contract should be designed from actual product requirements before being exposed publicly.
