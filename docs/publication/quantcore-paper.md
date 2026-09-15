# QUANTCORE: A Point-in-Time and Reproducible Framework for Quantitative US Equity Research

**Manuscript status:** structured research draft. Empirical results are intentionally pending until the evaluation protocol is executed and the resulting artifacts are versioned.

## Abstract

Quantitative equity research depends not only on statistical methodology but also on whether historical inputs represent the information that was actually available at the time of a decision. Revised financial statements, corporate-action updates, filing timestamps, changing security identities, and mutable datasets can introduce look-ahead bias or make apparently identical experiments irreproducible. QUANTCORE is a software framework designed to address these engineering and methodological concerns for US equity research. Its deterministic research pipeline combines canonical financial data, explicit point-in-time semantics, revision-aware observations, historical dataset construction, versioned factor/signal/strategy contracts, portfolio analytics, backtesting, and experiment provenance. Research datasets and experiment objects expose canonical identities and deterministic fingerprints so that research inputs and outputs can be audited and reproduced. A versioned API exposes the research capabilities as explicit service contracts. This manuscript presents the system architecture, temporal model, reproducibility design, quantitative research pipeline, and planned empirical evaluation. The agentic AI layer is intentionally treated as a future orchestration layer over the deterministic research substrate rather than as a replacement for it.

**Keywords:** quantitative equity research, point-in-time data, reproducibility, backtesting, factor investing, research infrastructure, financial data engineering, AI-assisted research

## 1. Introduction

Quantitative equity research systems often combine heterogeneous market and financial datasets with statistical transformations, portfolio construction, and historical evaluation. A central difficulty is temporal: a value that is correct today may not have been knowable on a historical research date. Treating current values as historical truth can contaminate factor calculations and backtests with information that arrived later. Related work on data snooping and backtest selection also shows why historical performance should not be interpreted independently of the research-selection process [2–6].

A second difficulty is reproducibility. A research result may depend on mutable source data, ambiguous identifiers, implicit configuration, unordered collections, or undocumented transformations. Reproducible computational research therefore requires enough information to reconstruct the computational path rather than only reporting a final result [1]. In such systems, reproducing a published result can require reconstructing hidden assumptions rather than replaying an explicit research definition.

QUANTCORE is designed as a research-engineering framework in which temporal semantics, deterministic identity, and analytical boundaries are first-class concerns. The system provides a canonical data layer and a research pipeline that proceeds from point-in-time observations through datasets, factors, signals, strategies, portfolios, backtests, and experiment artifacts.

Established empirical asset-pricing research provides context for the factor and portfolio layers, including the Fama–French factor tradition [7,8]. QuantCore does not claim to discover or validate any published factor premium merely by implementing a configurable factor pipeline.

### Contributions

The intended contributions of the system are:

1. A revision-aware point-in-time data model for historical equity research.
2. Explicit temporal alignment across market, financial-statement, and corporate-action observations.
3. Deterministic research dataset and experiment identity/fingerprinting.
4. A modular quantitative research pipeline with explicit contracts between factors, signals, strategies, portfolios, and backtests.
5. A product API that exposes these analytical capabilities without moving research methodology into HTTP handlers.
6. A foundation for future agentic research orchestration in which an AI system operates validated research tools rather than generating financial facts independently.

## 2. System architecture

QUANTCORE is implemented as a layered Python backend. API endpoints provide transport and authorization boundaries; services contain domain and research logic; repositories contain persistence/query behavior; processing components normalize and validate data; and provider adapters isolate external sources.

```text
External sources
      |
      v
Provider adapters
      |
      v
Ingestion / processing / validation
      |
      v
Canonical persistence + provenance + revisions
      |
      v
Point-in-time alignment
      |
      v
Research observations / datasets
      |
      +----> factors -> panels -> returns/evaluation
      |
      +----> signals -> strategies -> portfolios
                                      |
                        +-------------+-------------+
                        |             |             |
                      risk         stress       transition/cost
                        |             |             |
                        +-------------+-------------+
                                      |
                                   backtest
                                      |
                             performance/attribution
                                      |
                                  experiments
```

The architecture intentionally separates analytical methodology from delivery mechanisms. The HTTP API is therefore not itself the research engine.

## 3. Point-in-time data model

The temporal model distinguishes several concepts that are often conflated in financial systems. Revision-aware observations include explicit `known_at` semantics. SEC filing observations retain filing identity where supplied, and research calculations operate against an explicit `as_of` timestamp.

The intended selection rule is conceptually:

```text
candidate observations
        |
        +--> economically/period appropriate
        |
        +--> known by research as_of
        |
        +--> compatible with PIT alignment rules
        |
        v
PIT-aligned research snapshot
```

The purpose is not to reconstruct an omniscient historical database. It is to prevent later-known information from silently entering a historical research calculation.

## 4. Canonical research datasets

Historical dataset construction normalizes symbols, research dates, and definition identities. Dataset rows and feature vectors are canonicalized before fingerprinting. This provides an explicit identity for the research input rather than relying only on a human-readable dataset name.

The reproducibility chain can therefore be represented as:

```text
PIT observations
   -> feature vector
   -> factor/signal/strategy inputs
   -> historical dataset fingerprint
   -> experiment execution input
```

## 5. Factors and signals

Factor definitions and calculators are versioned and registered explicitly. Factor computation validates alignment between feature vectors and definitions. Cross-sectional factor panels preserve the research date and universe and use deterministic ranking behavior.

Forward factor returns use price observations strictly after the factor observation timestamp. The implementation explicitly handles unavailable horizons rather than silently manufacturing labels.

Signals consume ranked factor information and normalize contributions into deterministic signal rows. The signal layer does not own portfolio or execution semantics.

## 6. Strategies and portfolios

Strategies are declarative objects connecting a signal identity with direction and thresholds. Portfolio construction translates a validated strategy into target weights using deterministic construction rules. Risk, factor risk, constraints, rebalance analysis, transaction-cost calculation, and stress analysis are separate services.

Stress testing is deliberately defined as a hypothetical deterministic scenario engine. It applies explicit security-level/default shocks to an already constructed portfolio and reports position and aggregate effects. It is not presented as a probabilistic forecast.

## 7. Backtesting and attribution

Backtesting consumes explicit target portfolios and market observations together with rebalance, constraint, and transaction-cost definitions. Performance analytics operate on backtest results, while attribution provides period/position explanations. This separation allows each layer to be tested independently and prevents reporting code from silently changing the backtest methodology.

## 8. Experiment reproducibility

Research experiments have explicit definitions, input fingerprints, execution identities, results, artifacts, provenance, selections, and comparisons. Experiment runs can be bound to concrete dataset snapshots. Persistent experiment resources are owner-scoped.

A reproducible experiment should therefore record:

```text
software version/commit
+ research definition versions
+ dataset identity/fingerprint
+ execution input identity
+ result fingerprint
+ artifact/provenance identity
```

## 9. API architecture

The product API exposes research operations through versioned FastAPI routers. Protected research operations use OIDC authentication and the `research:read` scope in the current implementation. Endpoints remain thin and translate HTTP contracts into service-layer contracts.

The experiment HTTP surface is currently read-oriented. Execution orchestration is intentionally not exposed through a generic endpoint until a concrete asynchronous/product contract is justified.

## 10. Software verification

The repository contains tests across API, service, repository, processing, model, and research layers. The latest development checkpoint reported 1329 passing tests with one warning. This establishes software verification at that checkpoint; it is not evidence by itself of economic validity.

The final publication evaluation will archive the exact software commit, test results, experiment definitions, and research artifacts used for every reported empirical result.

## 11. Empirical evaluation plan

The evaluation will focus first on methodological validity:

### 11.1 PIT integrity

Construct controlled cases containing revisions that occur after the research date and verify that PIT-aligned calculations exclude later information.

### 11.2 Determinism

Repeat identical research runs and verify equality of canonical payloads and fingerprints. Perturb individual inputs and verify the expected identity changes.

### 11.3 Analytical reconciliation

Verify portfolio, factor-return, transaction-cost, backtest, performance, attribution, and stress aggregation invariants.

### 11.4 Historical strategy evaluation

Only after the methodology tests pass should empirical strategy experiments be reported. Because factor research is vulnerable to data snooping and multiple testing [4,5], the experiment record should preserve the candidate-search process and distinguish pre-specified tests from exploratory analysis. The evaluation should use explicitly documented universes, PIT datasets, construction rules, horizons, transaction-cost assumptions, and out-of-sample methodology.

### 11.5 Robustness

Where appropriate, report sensitivity to definitions, horizons, costs, universe rules, and other methodological assumptions. Implementation costs must be treated as part of the empirical design rather than as an afterthought [10,11]. Avoid presenting a single selected backtest as conclusive evidence; published predictors can also experience weaker out-of-sample or post-publication performance [9].

**No empirical performance result is claimed in this draft.**

## 12. Agentic AI as future work

The future AI layer is designed to operate above the deterministic research substrate. An agent may interpret a research request, decompose it into tool calls, execute validated research operations, compare results, inspect provenance, and synthesize an explanation. It should not bypass point-in-time constraints or invent financial observations.

The intended relationship is:

```text
User research question
        |
        v
Agent planning / tool selection
        |
        v
Validated QuantCore research contracts
        |
        v
Deterministic evidence + provenance
        |
        v
Agent reasoning / synthesis
```

This separation is important because an AI-generated explanation and a quantitatively computed result have different epistemic roles.

## 13. Limitations

The current system is a research platform rather than a live trading/execution system. Provider coverage, licensing, historical completeness, and real-time market-data semantics remain production concerns. The current implementation does not claim complete US-security coverage. Stress analysis is hypothetical rather than probabilistic. The agentic AI and institutional frontend are future phases.

## 14. Reproducibility and artifact release

For publication, each reported experiment should be associated with a software commit and a machine-readable experiment manifest containing the relevant research identities and fingerprints. Figures and tables should be generated from archived result artifacts rather than manually transcribed values.

Underlying third-party financial data should only be redistributed where the applicable provider license permits it. Otherwise, the publication package should provide identifiers, transformations, and reproduction instructions without redistributing restricted raw data.

## 15. Conclusion

QUANTCORE presents a software architecture for quantitative US equity research in which historical information availability, deterministic identity, and analytical separation are treated as core research requirements. The framework is intended to provide a stable substrate on which reproducible quantitative analysis can be conducted and, later, an agentic AI system can orchestrate research workflows. The next scientific step is empirical validation of the PIT and reproducibility claims followed by carefully controlled financial-research experiments.

## References

The current curated literature set is maintained in [publication references](references.md). The manuscript should not be treated as submission-ready until the literature review is expanded for point-in-time financial data, look-ahead and survivorship bias, reproducible computational research, factor investing, backtesting methodology, transaction costs, and—only if the AI layer becomes part of the paper—AI-assisted financial research.
