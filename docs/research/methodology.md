# Research Methodology

## Research observation read and point-in-time semantics

Research observations are immutable, derived values bound to an explicit
`as_of` knowledge boundary. Exact reads by security and `as_of` return only
observations recorded at that boundary. PIT reads may instead request the
latest stored observation for each `(observation_key, definition_version)`
known at or before a requested boundary.

The PIT read does not recalculate an observation, rewrite its input manifest,
or manufacture missing historical observations. It only selects from
observations that QuantCore actually persisted. Definition versions remain
separate identities, so introducing a new definition version does not silently
replace an older research definition.

## Canonical research metric definitions

Canonical research metrics are registered as versioned, deterministic definitions
that operate on a `PITAlignedSnapshot`. The metric definition is part of the
observation identity through `(observation_key, definition_version)` and is
recorded in the persisted input manifest so a later definition version cannot
silently reinterpret an older observation.

The initial canonical set is intentionally small and uses only fields already
present in the PIT financial-statement revisions:

- `net_margin` v1 = TTM net income / TTM total revenue.
- `operating_margin` v1 = TTM operating income / TTM total revenue.
- `fcf_margin` v1 = TTM free cash flow / TTM total revenue. The income and
  cash-flow TTM rows must share the same fiscal date.
- `debt_to_equity` v1 = latest PIT-known total debt / total equity from an
  `INSTANT` balance-sheet observation.

Definitions do not fall back from a required period type to another period
semantics. Missing required inputs are therefore explicit computation failures,
and zero denominators are rejected rather than producing an undefined ratio.
Each computed observation records the selected statement/revision identifiers,
fiscal date, period type, knowledge timestamp, and formula fields in its input
manifest. The canonical registry is loaded by default by
`ResearchObservationDefinitionService`; callers can still provide an explicit
set of definitions when isolated or alternative research definitions are
required.

## Research metric computation and observation materialization

Research metric materialization computes a selected set of versioned definitions
from one shared `PITAlignedSnapshot` and persists the resulting observations
through the existing immutable observation service. When no identities are
supplied, the registered canonical definitions are materialized in registry
order; callers can instead provide explicit `(observation_key,
definition_version)` identities.

The materializer resolves and validates all requested definitions before reading
the PIT snapshot, computes every result before persisting any result, and does
not commit the database transaction. This keeps the PIT boundary shared across
the batch, prevents definition failures from causing partial persistence within
the materialization operation, and leaves transaction ownership with the
calling workflow. Input manifests continue to carry the definition identity,
shared PIT snapshot metadata, and definition-specific source/formula provenance.


## Research dataset and feature-vector contract

The research dataset layer is a read-only projection over materialized research
observations. `ResearchDatasetService` builds a `ResearchFeatureVector` for one
security and one requested `as_of` boundary; it does not compute new metrics or
persist dataset rows.

A feature vector contains:

- normalized security symbol and stable `security_id`
- the requested `as_of` knowledge boundary
- an ordered tuple of `ResearchFeature` values
- each feature's `(observation_key, definition_version)` identity
- the selected observation's own `as_of` timestamp
- numeric/text value and unit
- the observation input fingerprint and input manifest for provenance

By default, the service selects the latest stored observation for each versioned
definition known at or before the requested boundary, using the existing PIT
research-observation read contract. Explicit definition identities can instead
be requested when a downstream research workflow needs a fixed feature schema.
Explicit identities are returned in caller order; the default vector is sorted
by observation key and definition version for deterministic output.

The feature-vector layer fails when a requested feature has not been materialized,
when the materialized read is empty, or when an observation would violate the
requested `as_of` boundary. It does not backfill missing observations, mix
securities, or silently substitute another definition version. This contract is
intentionally in-memory and non-persistent; historical research panels,
factor definitions, cross-sectional ranking, and portfolio construction are
later layers built above it.

## Historical research analysis and dataset consumption

The historical research analysis layer consumes `ResearchFeatureVector` values
without recomputing or persisting research data. `ResearchHistoricalAnalysisService`
builds an immutable historical dataset for an explicit set of symbols and
point-in-time timestamps. Each requested symbol/timestamp pair becomes one
`ResearchHistoricalDatasetRow`; missing materialized data is an error rather
than a reason to silently drop a row.

The service normalizes symbols and timestamps, rejects duplicate symbols or
timestamps, rejects future boundaries, and validates an optional fixed set of
versioned definition identities before performing any dataset reads. Output is
deterministically ordered by `as_of` and normalized symbol. Explicit definition
identities are passed unchanged to the feature-vector layer after normalization,
so every historical row uses the same feature schema.

This boundary is intentionally read-only and in-memory. It establishes the
historical research panel consumed by later factor definitions, cross-sectional
ranking, signal generation, and portfolio construction without introducing
look-ahead selection, feature recomputation, or a second persistence model.

## Research factor definition and identity contract

Research factors are versioned research definitions built above the historical
research dataset. A factor is identified by `(factor_key, definition_version)`;
changing the meaning or required inputs of a factor therefore requires a new
factor definition version rather than silently changing an existing identity.

`ResearchFactorDefinition` declares the ordered versioned observation identities
required from the research feature vector and the expected factor output kind
(`numeric` or `text`). It may also declare an output unit and a human-readable
description. Required feature identities must be unique and fully versioned.

`ResearchFactorDefinitionRegistry` resolves these definitions in memory and
rejects duplicate identities or unknown versions. This layer contains no factor
calculation, ranking, normalization, or persistence. The later factor-computation
layer is responsible for consuming the declared features and producing the
factor value while preserving the historical/PIT boundary established below it.

## Cross-sectional research factor panels

The cross-sectional factor-panel layer consumes the immutable historical research
panel and the versioned factor-computation contract. `ResearchFactorPanelService`
computes one requested `(factor_key, definition_version)` for every historical
security/as-of row and returns an in-memory `ResearchFactorPanel` ordered by
`as_of`, normalized symbol, and stable `security_id`.

The panel requires a non-empty historical dataset and rejects duplicate
security/as-of points, future boundaries, row/feature-vector identity mismatches,
and inconsistent factor units. Factor values retain the factor-computation
provenance manifest, so panel construction does not discard the PIT inputs that
produced each value.

This layer is deliberately descriptive rather than analytical: it does not rank,
standardize, winsorize, neutralize, construct signals, persist factor values, or
build portfolios. Those operations belong to later research-analysis layers.

## Cross-sectional factor ranking and normalization

The next research-analysis layer consumes the descriptive factor panel without
reading from persistence or recomputing factor inputs. `ResearchFactorCrossSectionalService`
ranks numeric factor values independently within each `as_of` cross-section. This is
important: securities from different research dates are never ranked against one another.

The initial ranking contract uses an explicit average-tie convention. With
`higher_is_better=True`, the largest factor receives rank 1; with `False`, the smallest
factor receives rank 1. Ties receive the arithmetic mean of their occupied 1-based ranks.
The service also emits a unitless `normalized_rank` in [0, 1], where the best observation
is 1 and the worst is 0. A singleton cross-section receives 0.5 because relative ordering
cannot be inferred from one observation.

Text factors, non-finite numeric values, duplicate security/as-of points, and empty panels
are rejected. The transformation remains in-memory and deterministic; it does not persist
ranks, construct signals, evaluate predictive performance, or build portfolios.

## Factor evaluation

`ResearchFactorEvaluationService` consumes the rank-normalized factor panel and produces deterministic cross-sectional diagnostics independently for each `as_of`. It reports observation counts, mean, median, population standard deviation, minimum, maximum, and range per cross-section, plus aggregate summaries across cross-sections.

This layer is descriptive quality evaluation only. It does not estimate forward returns, information coefficients, factor returns, signals, or portfolios; those require explicit future-return and strategy contracts in later research layers.

## Factor returns and forward-return alignment

`ResearchFactorReturnService` aligns each rank-normalized factor observation with a
realized forward return outcome. The factor observation's `as_of` timestamp is an
information boundary: the entry price is the first available price observation
strictly after that timestamp. The exit price is `horizon` trading observations
later, so the future price is an outcome label and is never used to construct the
factor observation itself.

The initial contract supports `PriceBasis.UNADJUSTED` using `close` and
`PriceBasis.ADJUSTED` using `adjusted_close`. Adjusted returns require an adjusted
close on every selected observation; the service never silently mixes price bases.
A missing future horizon is retained as an explicit `HORIZON_UNAVAILABLE` row
rather than silently dropping the factor observation. The service is in-memory and
non-persistent; factor return aggregation, predictive statistics, and signal
construction remain later contracts.

## Factor return methodology

`ResearchFactorReturnMethodologyService` converts aligned forward-return outcomes into a
cross-sectional factor-return series using an explicit rank-ordered, equal-weighted
long/short methodology. Bucket membership is determined from the factor ranks before
future-return availability is considered; unavailable outcomes therefore cannot change
factor-based membership. The default configuration is five buckets (quintiles), with the
best-ranked bucket as the long leg and the worst-ranked bucket as the short leg. Bucket
sizes are deterministic and as even as possible, with earlier buckets receiving any
remainder.

The reported factor return is `mean(long forward returns) - mean(short forward returns)`.
Only rows with an `AVAILABLE` forward-return outcome contribute to a bucket return, while
all original observations remain represented for coverage diagnostics. Minimum eligible
observations per leg is explicit and insufficient coverage yields a non-returning status
rather than a fabricated spread. This layer is research analytics only: it does not apply
transaction costs, portfolio constraints, sector/beta neutralization, execution assumptions,
or persistence. Those concerns belong to later strategy/portfolio layers.

## Research signal construction

`ResearchSignalService` consumes one or more rank-normalized research factor panels and
constructs a deterministic composite research signal. A `ResearchSignalDefinition` identifies
the versioned factor inputs and requires explicit strictly-positive weights that sum to one.

All input factors must share the exact same security/as-of universe. This is intentional: a
missing factor observation must not silently change the universe or cause the remaining weights
to be re-normalized. Each signal row preserves per-factor normalized rank, weight, and weighted
contribution for provenance.

The composite `score` is the weighted average of normalized ranks and is therefore in `[0, 1]`.
`centered_score` maps that value to `[-1, 1]` for downstream research consumers. The service does
not construct portfolios, orders, execution instructions, or transaction-cost assumptions; those
belong to later strategy and portfolio layers.

## Strategy definition

`ResearchStrategyDefinition` establishes the declarative strategy contract above the research-signal
layer. A strategy is identified by `(strategy_key, definition_version)` and explicitly references
a versioned research signal. The definition declares whether the signal is interpreted as
`LONG_ONLY`, `SHORT_ONLY`, or `LONG_SHORT` and, where applicable, provides score thresholds in
the signal's `[0, 1]` domain.

This boundary is deliberately declarative. It does not construct holdings or portfolio weights,
choose a rebalance schedule, apply constraints, model transaction costs, create orders, or encode
execution assumptions. Those concerns belong to the subsequent portfolio-construction and
rebalancing layers. Threshold validation is deterministic and versioned so a strategy's meaning
cannot silently change under an existing identity.

## Portfolio construction

`ResearchPortfolioConstructionService` converts a versioned `ResearchStrategyDefinition`
and its matching `ResearchSignalPanel` into deterministic target portfolio weights at one
explicit, timezone-aware `as_of` information boundary. The signal identity must exactly match
the strategy identity, and duplicate security/as-of points are rejected.

Long-only strategies select signal scores greater than or equal to the configured long threshold
and assign equal positive weights summing to one. Short-only strategies select scores less than
or equal to the short threshold and assign equal negative weights summing to negative one.
Long-short strategies require both legs to be populated; each leg is equal-weighted with equal
absolute dollar exposure, producing gross exposure of two and net exposure of zero. If a
long-short leg is empty, no target positions are emitted and the result explicitly reports
`INCOMPLETE_LONG_SHORT` rather than silently creating an unbalanced portfolio.

The output contains target weights, not orders or executions. This layer does not apply portfolio
constraints, turnover limits, rebalance schedules, transaction costs, liquidity assumptions, broker
semantics, or persistence; those belong to subsequent portfolio and execution boundaries.

## Portfolio constraints

`ResearchPortfolioConstraintDefinition` is a versioned, declarative set of portfolio-level limits,
and `ResearchPortfolioConstraintService` validates a target `ResearchPortfolio` without modifying
its weights. Supported limits are maximum absolute position weight, maximum gross exposure, signed
minimum/maximum net exposure, maximum long exposure, and maximum short exposure. At least one limit
must be configured, and all limits are deterministic and immutable under a constraint identity.

Validation reports every violated rule together with its observed value and configured limit. A
passing result does not rewrite or rebalance the portfolio; constraint enforcement remains a distinct
methodology decision. Empty target portfolios pass exposure constraints because there is no exposure
to violate a configured limit. This layer does not choose rebalance schedules, optimize weights,
apply turnover or transaction costs, or create orders/execution instructions.


## Portfolio rebalancing

`ResearchRebalanceService` converts a current target-portfolio state and a new constructed target
portfolio into a deterministic set of non-zero weight transitions at an explicit, timezone-aware
rebalance `as_of`. A versioned `ResearchRebalanceDefinition` records the declared evaluation cadence
(`DAILY`, `WEEKLY`, or `MONTHLY`) without inventing calendar dates or performing scheduling itself.

The rebalance result preserves strategy, signal, and rebalance provenance, reports current and target
exposures, and calculates one-way weight turnover as `0.5 * sum(abs(target_weight - current_weight))`.
Transitions are classified as `ADD`, `INCREASE`, `REDUCE`, `REMOVE`, or `REVERSE` and are emitted in
deterministic security-id order; zero-delta holdings are omitted. The service requires the current
portfolio to precede the rebalance boundary and the target portfolio to exist exactly at that boundary.
Only a `CONSTRUCTED` target portfolio may be rebalanced. This layer does not calculate transaction costs,
slippage, market impact, orders, fills, broker instructions, or execution semantics.

## Transaction costs

`ResearchTransactionCostService` converts a versioned proportional transaction-cost definition and a validated `ResearchRebalance` into a deterministic portfolio cost. The initial model expresses a one-way cost rate in basis points and applies it to the rebalance's one-way weight turnover: `cost_bps = turnover * one_way_cost_bps`, with `cost_fraction = cost_bps / 10,000`.

The result preserves rebalance, strategy, signal, and cost-definition provenance and reports an explicit `NO_TURNOVER` status when the transition has zero turnover. This boundary does not invent dollar commissions, bid/ask spreads, slippage, market impact, execution prices, orders, fills, or broker semantics because the current research rebalance contract does not contain the required execution inputs. Richer cost models can be added as separate versioned methodologies later.

## Backtesting

`ResearchBacktestService` runs a deterministic weight-based historical backtest from an ordered
sequence of constructed target portfolios at explicit `as_of` boundaries. The first target
establishes the initial allocation; each later target is treated as the next rebalance boundary.
Historical valuation uses the first available price strictly after each period boundary, preserving
the information-boundary convention used by forward-return research. The configured `PriceBasis`
must be used consistently, and missing or invalid historical prices are explicit input failures.

Each period records starting and ending equity, gross return, transaction-cost fraction, net return,
turnover, and completion status. Transaction costs are consumed from the versioned rebalance
transition rather than recomputed. Portfolio constraints are validated at every target boundary
before the backtest proceeds. The first implementation deliberately uses successive target weights
for turnover and does not model intra-period weight drift, share-level fills, slippage, market impact,
risk metrics, attribution, or order execution. Those are separate future methodologies.

## Backtest performance analytics

`ResearchBacktestPerformanceService` derives deterministic performance and realized-risk
metrics from a completed `ResearchBacktest` without fetching new data or changing the
strategy. It reports total return, CAGR-style annualized return over the backtest calendar
interval, annualized realized log-return volatility, maximum drawdown, maximum drawdown
duration, average period return, win/loss/flat period counts, win rate, and average turnover.

Volatility is based on each completed period's log return converted to an annualized rate
and weighted by elapsed calendar time, so the methodology does not assume that every
backtest period has identical length. Drawdown is measured from the running equity peak,
starting at initial capital. These metrics describe realized historical behavior only;
they do not constitute a risk forecast, factor-risk model, stress test, or execution model.


## Backtest portfolio attribution

`ResearchBacktestAttributionService` decomposes realized historical return for each
completed backtest period into security-level gross contributions and transaction-cost
drag. Position contribution is target weight multiplied by the realized security return
between the same valuation boundaries used by the backtest. Long and short contributions
are reported separately and reconcile to gross return for each period. Contributions are
also capital-scaled by each period's starting equity so the complete backtest attribution
reconciles additively to total net return. `total_gross_return` and
`total_transaction_cost_drag` are additive contributions relative to initial capital, not
compounded standalone performance series; transaction-cost drag remains the exact period
difference between recorded net and gross return.

The service requires the target portfolio used at each period start and the same historical
price basis as the backtest. It does not allocate transaction costs to individual
securities, infer causal effects, forecast returns, or change portfolio weights.

## Portfolio risk and exposure analytics

`ResearchPortfolioRiskService` produces a deterministic descriptive risk snapshot from an existing
`ResearchPortfolio` without changing the portfolio or accessing market data. It reports position
counts, long/short/gross/net exposure, maximum absolute position weight, net-to-gross exposure ratio,
and weight concentration using Herfindahl-Hirschman Index (HHI) with its corresponding effective
position count. Long and short legs also receive separate concentration metrics.

Concentration is calculated from absolute portfolio weights normalized within the relevant gross,
long, or short exposure. An empty portfolio has zero exposure and zero concentration; no artificial
risk is inferred. The snapshot is an exposure representation, not a return forecast or covariance
model. It does not calculate volatility, factor exposures, stress losses, liquidity risk, transaction
costs, or execution outcomes; those are separate risk methodologies.

## Portfolio factor-risk analytics

`ResearchPortfolioFactorRiskService` computes deterministic rank-based factor exposures for an existing constructed portfolio using versioned, rank-normalized factor panels at the portfolio's exact `as_of` boundary. Each factor exposure is the signed portfolio-weighted sum of centered normalized ranks, with separate long/short contributions, gross factor contribution, and gross-normalized exposure.

This is a descriptive factor-loading representation on the existing rank scale. It is not a regression beta, covariance model, factor return forecast, or stress model. Missing factor observations for held securities, duplicate observations, identity mismatches, and invalid ranks are explicit input failures. The service does not mutate portfolios, fetch market data, forecast returns, or perform execution.

## Portfolio scenario and stress-risk analytics

`ResearchPortfolioStressService` applies a versioned, deterministic hypothetical return-shock scenario to an existing constructed target portfolio. A scenario can provide security-specific shocks and may optionally define a default shock for broad scenarios such as a market selloff; security-specific values take precedence. Each position's stress contribution is its target weight multiplied by the scenario return shock, so long and short directions are preserved explicitly.

The result reports the aggregate hypothetical portfolio return, optional capital-scaled P&L and stressed value, and security-level contributions with strategy, signal, scenario, and `as_of` provenance. When no default shock is configured, every held security must have an explicit shock. Shocks below -100% are rejected. This is a deterministic what-if analysis, not a forecast, historical observation, covariance model, factor model, liquidity model, or execution simulation; it does not fetch data or mutate portfolio weights.
