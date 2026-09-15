# Scientific Evaluation Protocol

The [scientific evidence matrix](evidence-matrix.md) is the companion control document for distinguishing implemented software behavior from claims that require empirical evidence.

This document separates **software verification** from **financial-research evaluation**. Passing tests demonstrates implementation consistency; it does not establish that a factor or strategy generates economic alpha.

## 1. Software verification

The current development checkpoint has a broad automated test suite covering API contracts, services, repositories, processing, models, and research methodology. The latest local checkpoint reported **1329 passing tests with one warning**. This number is a development checkpoint and should not be hard-coded as a permanent project statistic.

The minimum verification sequence for a release candidate is:

```bash
cd backend
uv run python -m compileall -q src tests
uv run pytest -q
```

Additional focused tests should be run for every changed research/API boundary.

## 2. PIT integrity evaluation

The primary methodological experiment should construct controlled historical cases where a later revision differs from the information available at the research date.

Compare:

```text
naive/latest-value calculation
vs.
PIT-aligned calculation
```

The experiment should measure whether the two paths produce different research inputs/results and verify that the PIT path excludes information whose `known_at`/filing semantics occur after the research `as_of`.

This is a methodology validation experiment, not an assertion that the naive path exists as a production QuantCore feature.

## 3. Reproducibility evaluation

Run identical research definitions against identical versioned inputs multiple times. Verify:

- canonical payload equality;
- dataset fingerprint equality;
- execution-input fingerprint equality;
- result fingerprint equality where applicable;
- artifact/provenance identity equality.

Then perturb one controlled input at a time and verify that the relevant identity changes.

## 4. Analytical reconciliation

The evaluation suite should verify internal accounting relationships, including:

- portfolio weights and side-magnitude invariants;
- factor panel universe/`as_of` alignment;
- factor-return entry/exit horizon semantics;
- transaction-cost calculations;
- backtest period continuity;
- performance totals;
- attribution reconciliation;
- stress position contributions and portfolio aggregation.

## 5. Research methodology evaluation

For factors and signals, the empirical evaluation should report methodology rather than only headline returns. At minimum, record:

- universe definition;
- observation dates;
- PIT dataset identity;
- factor definition/version;
- signal definition/version;
- portfolio construction rule;
- rebalance rule;
- transaction-cost assumptions;
- evaluation horizon;
- missing-data policy;
- survivorship/universe policy;
- benchmark definition where applicable.

## 6. Statistical evaluation

The final paper should use appropriate out-of-sample methodology and should avoid presenting a single selected backtest as evidence of general predictive validity. The evaluation should explicitly account for:

- pre-declared in-sample and out-of-sample periods;
- the number and nature of strategy/factor configurations considered;
- multiple-testing or selection effects when many candidate specifications are examined;
- sensitivity to universe, horizon, costs, and other material assumptions;
- uncertainty measures appropriate to the research design; and
- external or post-publication validation where the research question requires a claim of generalization.

Backtest selection itself is part of the evidence record. A favorable result selected after many unreported trials is not equivalent to a pre-specified out-of-sample result.

These experiments have **not yet been executed by this documentation change**. No numerical alpha, Sharpe ratio, drawdown, or predictive-performance claim should be added until the corresponding experiment is run and archived.

## 7. Publication artifacts

A publication-grade evaluation package should contain:

```text
experiment definition
        +
software commit
        +
dataset identity/fingerprint
        +
configuration
        +
execution metadata
        +
result/artifact fingerprints
        +
figures/tables generated from the same artifacts
```

Provider licensing and redistribution restrictions must be checked before distributing underlying market or financial data.
