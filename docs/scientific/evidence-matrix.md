# Scientific Evidence Matrix

This matrix is the control document for keeping technical claims aligned with repository evidence. It deliberately separates **implementation evidence** from **empirical evidence**: code and tests can establish software behavior, but they cannot by themselves establish economic alpha or predictive validity.

## Evidence classes

| Class | Meaning |
|---|---|
| **Implemented** | The capability exists in the current repository and has corresponding code/tests. |
| **Verification pending** | The repository contains the capability, but the release checkpoint still requires execution in the supported environment. |
| **Empirical evidence required** | A scientific claim requires a controlled experiment and archived results; implementation alone is insufficient. |
| **Future** | The capability is intentionally planned but not implemented in the current checkpoint. |

## Current evidence map

| Claim / capability | Status | Repository evidence | Publication treatment |
|---|---|---|---|
| Point-in-time market/financial/corporate-action alignment | Implemented | `backend/src/quantcore/services/pit_alignment_service.py`; revision repositories; PIT-focused service tests | May be described as an implemented methodological capability. Quantitative effectiveness still requires controlled PIT evaluation. |
| SEC filing/XBRL temporal semantics | Implemented | SEC services/repositories/models and related service/API tests | Describe the temporal model precisely; do not imply complete historical capture beyond ingested data. |
| Historical research datasets and deterministic feature identities | Implemented | `research_dataset_service.py`; research feature/dataset schemas and service tests | May be described as implemented reproducibility infrastructure. |
| Deterministic factor panels, ranking, evaluation, and forward returns | Implemented | `research_factor_*` services and corresponding tests | Methodology may be described; economic predictive validity requires empirical experiments. |
| Deterministic signals, strategies, and portfolio construction | Implemented | `research_signal_service.py`, `research_strategy_service.py`, `research_portfolio_construction_service.py` and tests | Describe construction semantics; do not claim investment performance. |
| Portfolio risk, factor risk, constraints, rebalance, transaction costs, and stress analysis | Implemented | Corresponding services, product services, API endpoints, schemas, and tests | Stress must remain described as hypothetical/deterministic, not probabilistic forecasting. |
| Deterministic backtesting, performance, and attribution | Implemented | `research_backtest*` services/product services, API endpoints, schemas, and tests | Describe software capability; performance claims require archived experiments. |
| Experiment identities, runs, results, artifacts, provenance, comparisons, and ownership boundaries | Implemented | `research_experiment_service.py`, experiment repository/API, ownership tests | May be described as research-record infrastructure. Report exact manifests/fingerprints for published experiments. |
| Versioned research product API | Implemented | 21 research endpoint modules under `backend/src/quantcore/api/endpoints/`; API tests | API surface can be documented as implemented; deployment availability is a separate release concern. |
| OIDC authentication and research authorization | Implemented | `backend/src/quantcore/api/auth.py`, authorization dependencies, API auth/authorization tests | Describe the implemented resource-server boundary without claiming complete production security certification. |
| Production data coverage and licensing | Verification pending / empirical & operational | `docs/data-sources.md`; provider adapters and ingestion services | Do not claim complete US-market coverage or unrestricted redistribution. Source-specific evidence and licenses must be frozen for release. |
| PIT integrity experiment | Empirical evidence required | Protocol in `docs/scientific/evaluation.md` | Do not claim measured bias reduction until the controlled experiment is executed and archived. |
| Deterministic reproducibility experiment | Empirical evidence required | Protocol in `docs/scientific/evaluation.md` and fingerprint contracts | Report repeated-run and perturbation results only after execution. |
| Historical strategy performance | Empirical evidence required | Backtest implementation + evaluation protocol | No alpha, Sharpe, drawdown, or predictive-validity claim without archived experimental evidence. |
| Agentic AI research orchestration | Future | No agent runtime is represented as implemented in the current repository | Present as future work / planned architecture until implemented and separately evaluated. |
| Institutional research frontend | Future | `frontend/` is currently empty | Present as future product layer, not an existing application. |
| Public cloud deployment / AWS production hosting | Future | `deployment/` and `infrastructure/` are currently empty | Present as future release work, not current infrastructure. |

## Claim discipline

For the journal manuscript:

1. **Implementation claims** must point to repository artifacts and tests.
2. **Methodological claims** must state the exact temporal and data assumptions.
3. **Empirical claims** must point to archived experiment definitions, datasets, results, and generated figures/tables.
4. **Future architecture** must never be written in the present tense as completed functionality.
5. A passing software test suite is evidence of software behavior, not evidence of economic profitability.

## Release evidence package

Before a public scientific release, the evidence package should associate each reported result with:

```text
software commit
    +
research definition/version
    +
PIT dataset identity/fingerprint
    +
experiment execution identity
    +
result/artifact fingerprint
    +
generated table/figure
    +
data licensing decision
```

This matrix should be updated whenever a capability changes status or a new empirical result is introduced.
