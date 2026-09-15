# Publication

The publication track documents QuantCore as a research-engineering contribution rather than as a marketing case study. The manuscript should be treated as a scientific document whose implementation claims, methodological claims, and empirical claims have different evidence requirements.

## Manuscript

- [QuantCore manuscript draft](quantcore-paper.md)
- [Publication references](references.md)
- [Scientific evidence matrix](../scientific/evidence-matrix.md)
- [Scientific evaluation protocol](../scientific/evaluation.md)

## Publication workflow

The publication workflow is intentionally staged:

1. **Freeze the implemented software scope.**
   Record the exact software commit and supported execution environment.
2. **Freeze the methodological definitions.**
   Record the PIT assumptions, universe definition, research dates, factor/strategy versions, portfolio rules, cost assumptions, and missing-data policy.
3. **Run software verification.**
   Archive the exact test command and result from the supported environment.
4. **Run methodological experiments.**
   Execute PIT-integrity, determinism, and analytical-reconciliation experiments before reporting financial-performance results.
5. **Run empirical research experiments.**
   Use pre-declared evaluation windows and out-of-sample procedures; retain all relevant experiment definitions and artifacts.
6. **Generate publication artifacts from recorded results.**
   Tables and figures must be generated from the archived experiment outputs rather than manually transcribed.
7. **Perform a claim audit.**
   Every implementation, methodological, and empirical statement in the manuscript must map to repository evidence or an archived experiment.
8. **Apply the target journal's format and disclosure requirements.**
   The repository remains journal-agnostic until a specific venue is selected.

## Publication principles

1. Claims must be supported by the implementation or archived empirical evidence.
2. Software verification and financial-performance evaluation must be reported separately.
3. Historical experiments must identify the exact point-in-time dataset and research-date semantics used.
4. Reported figures and tables should be generated from versioned artifacts.
5. Third-party data must only be redistributed where the applicable license permits it.
6. Multiple-testing, backtest-selection, and implementation-cost risks must be addressed before interpreting historical performance as evidence of general predictive validity.
7. The future agentic AI layer should be evaluated separately from the deterministic research substrate.

## Current status

The manuscript is a structured draft, not yet a journal submission. The deterministic research software and product API are implemented substantially enough to document the engineering contribution, but the scientific evaluation package is incomplete.

Current publication blockers are:

- no archived PIT-integrity experiment results;
- no archived deterministic-reproducibility experiment results;
- no final empirical strategy evaluation;
- no generated publication figures/tables tied to archived artifacts;
- no final venue-specific literature and citation pass in the manuscript; the repository literature index now includes reproducibility, survivorship, missing-data, factor-replication, and recent look-ahead references;
- no final project license decision;
- no selected target journal and therefore no venue-specific formatting/disclosure package.

The absence of these items is deliberate and should remain visible rather than being hidden behind claims of publication readiness.
