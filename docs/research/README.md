# Research Methodology

QuantCore separates research methodology into explicit, composable stages. Each stage has its own definitions, validation rules, and identity where the implementation requires versioning.

The detailed methodology is maintained in [Research Methodology](methodology.md). This index provides the research pipeline at a glance and keeps the detailed technical contract separate from the documentation navigation layer.

## Research pipeline

1. **Point-in-time research input** — explicit `as_of` boundaries and domain-specific revision/filing semantics determine which observations were knowable at the research timestamp.
2. **Research observations** — canonical, versioned measurements are materialized from PIT-aligned snapshots with provenance.
3. **Historical datasets** — normalized symbols, timestamps, and feature identities form deterministic historical research datasets.
4. **Features and factors** — feature vectors and versioned factor definitions provide the inputs for factor computation.
5. **Cross-sectional panels and evaluation** — factor panels preserve security/date alignment; ranking and descriptive evaluation operate within each cross-section.
6. **Factor returns** — forward returns use prices strictly after the factor observation timestamp and retain unavailable horizons explicitly.
7. **Signals** — ranked factor information is transformed into deterministic normalized signal scores without portfolio or execution semantics.
8. **Strategies** — declarative strategy definitions connect signal identities to direction and thresholds.
9. **Portfolio construction** — validated strategies produce deterministic target weights without implying order execution.
10. **Portfolio analytics** — risk, factor risk, constraints, rebalance, transaction costs, and deterministic stress analysis remain separate analytical boundaries.
11. **Backtesting** — explicit portfolios, market observations, rebalance behavior, constraints, and transaction costs drive historical simulation; performance and attribution remain separate services.
12. **Experiments** — definitions, dataset bindings, execution identities, results, artifacts, provenance, and comparisons form the reproducible research record.

## Methodological boundaries

QuantCore currently does **not** claim:

- investment advice;
- live order execution;
- probabilistic stress forecasting;
- guaranteed alpha;
- complete coverage of every US security or data vendor;
- that a provider's freshness implies real-time market truth.

For source, ingestion, provenance, and temporal data-domain semantics, see [Data Sources](../data-sources.md). For canonical identities and reproduction procedures, see [Reproducibility](../reproducibility/README.md). For planned evidence and validation, see [Scientific Evaluation](../scientific/evaluation.md).
