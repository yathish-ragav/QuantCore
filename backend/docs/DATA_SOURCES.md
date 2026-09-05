# QuantCore Data Source Strategy

QuantCore will not treat one vendor as the truth for every dataset.
Each source has a defined responsibility, and the normalized domain layer
keeps provider-specific response formats out of the application.

## Source roles

| Dataset | Primary | Secondary / fallback | Purpose |
|---|---|---|---|
| US security universe | SEC EDGAR | FMP | CIK, ticker, exchange, issuer identity |
| Regulatory fundamentals | SEC EDGAR | FMP | 10-K/10-Q/XBRL facts |
| Balance sheet statements | SEC EDGAR | FMP | assets, liabilities, equity and derived capital structure facts |
| Income statements | SEC EDGAR | FMP | revenue, profitability and per-share fundamentals |
| Cash flow statements | SEC EDGAR | FMP | operating, investing, financing cash flow and free cash flow |
| Enriched fundamentals | FMP | SEC | standardized financial fields and ratios |
| Current quote | FMP | Polygon | dashboard snapshot |
| Real-time stream | Polygon | Nasdaq licensed feed | live charting / event-driven updates |
| Historical EOD | FMP / Polygon | Yahoo | research and backtesting |
| Corporate actions | Licensed market-data provider / FMP | Yahoo | dividends and stock splits; current adapter is secondary |
| Intraday | FMP / Polygon | Alpha Vantage | intraday charts and short-horizon analytics |
| News | Polygon / FMP | Yahoo | company and market news |
| Macro economics | FRED / ALFRED | FMP | rates, CPI, unemployment, GDP, etc. |
| Alternative / premium datasets | Nasdaq Data Link | vendor-specific | fundamentals, estimates, ratings and institutional datasets |

## Production rule

The UI must never assume that a number is "live" merely because it came from
a market-data library. Every live/near-live response should expose:

- source
- provider timestamp
- freshness/age
- market session
- whether the value is real-time, delayed, or historical

## Current implementation

The first production quote path is:

```text
GET /quotes/{symbol}
        |
        v
QuoteService
        |
        v
QuoteProviderFactory
        |
        v
FMP Quote API
        |
        v
QuoteData
```

This is deliberately separate from historical price ingestion.

## Planned real-time architecture

For production streaming:

```text
Exchange/SIP data
       |
   Polygon / licensed Nasdaq feed
       |
   WebSocket ingestion
       |
   event normalization
       |
   Redis / stream bus
       |
   Quote cache
       |
   FastAPI/WebSocket gateway
       |
   QuantCore UI
```

FMP remains useful for quote snapshots, fundamentals and broad financial
datasets. SEC remains the authoritative regulatory source for filings/XBRL.
Yahoo is retained as a useful secondary research source, not the authoritative
real-time market feed.

## Security master and universe rules

SEC's `company_tickers_exchange.json` is the current issuer/ticker/exchange
association source for the QuantCore universe. SEC documents that CIK is a
unique filer identifier and that the ticker/exchange association file is
periodically updated but does not guarantee complete accuracy or scope.
QuantCore therefore treats CIK as issuer identity, while ticker + exchange is
a current security listing identity. Tickers are not used as permanent
security primary keys.

The security master preserves lifecycle state (`ACTIVE` / `INACTIVE`) and
records observed ticker/exchange identities in a separate history table. A
listing that disappears from the managed universe is retired rather than
deleted, preserving historical references for later research and backtesting.

The current exchange filter is intentionally explicit. It represents
QuantCore's present managed listed-equity scope; it must not be described as
"all US securities" until additional instrument classifications and source
coverage are implemented and measured.


## Ingestion orchestration and freshness

QuantCore separates **data ingestion mechanics** from **ingestion scheduling**.

The existing dataset services remain responsible for:

1. provider selection,
2. external transport,
3. normalization,
4. cleaning and validation,
5. reconciliation,
6. persistence, and
7. transaction boundaries.

`IngestionOrchestrator` is responsible only for:

- selecting active securities from the managed universe,
- selecting datasets,
- deduplicating company-scoped work across multiple listings,
- deciding whether a dataset is stale,
- recording successful/failed attempts, and
- producing an auditable ingestion run summary.

Freshness is an ingestion property, not a claim that the underlying provider is
real-time. The current policies are:

| Dataset | Scope | Freshness window |
|---|---|---|
| Company metadata | Company | 7 days |
| Historical prices | Security | 1 day |
| News | Company | 6 hours |
| Income statement | Company | 1 day |
| Cash flow statement | Company | 1 day |
| Balance sheet | Company | 1 day |

These are scheduling defaults, not assertions about provider latency or market
status. Provider timestamps and market-session semantics remain a separate
market-data concern.

The current coordinator is intentionally synchronous and bounded. It is the
execution contract that a future worker/scheduler can call; Redis, Celery,
Kafka and WebSocket infrastructure are not introduced merely to make the
architecture diagram look complete.

## Ingestion health

QuantCore exposes a deterministic health classification on top of the existing
ingestion state. This is an operational signal, not a claim that the underlying
dataset is financially correct.

For a security symbol and each registered dataset, the health layer classifies
the latest known state as:

- `NEVER_INGESTED`: no successful ingestion has been recorded.
- `FAILED`: the latest attempt failed after the most recent success, or there
  has never been a successful ingestion.
- `STALE`: the last successful ingestion exists but is outside the dataset's
  configured freshness window.
- `HEALTHY`: the last successful ingestion is inside the freshness window and
  there is no outstanding failure state.

The overall symbol health is the worst dataset status. Classification is
derived from `IngestionOrchestrator.get_freshness()` and therefore does not
duplicate provider validation or persistence logic.

This layer is intentionally read-only: it does not mutate ingestion state,
retry work, or quarantine data. Dataset-level quality validation and
quarantine remain a separate concern so operational health is not confused
with financial-data correctness.

## Ingestion quality and completeness

Operational health and data quality are separate boundaries. The ingestion
quality layer measures execution coverage: how many eligible dataset targets
succeeded, were skipped because they were fresh, or failed.

Each ingestion run records its `eligible` target count. Company-scoped datasets
count unique companies even when multiple active securities belong to the same
issuer. Security-scoped datasets count unique securities.

The deterministic quality states are:

- `COMPLETE`: every eligible target succeeded or was validly skipped.
- `PARTIAL`: at least one target failed, but some coverage succeeded or was skipped.
- `FAILED`: every eligible target failed.
- `NO_TARGETS`: the selected scope contained no eligible targets.
- `INCONSISTENT`: persisted execution counters do not reconcile.

`coverage_ratio` is `(succeeded + skipped) / eligible`. A complete run therefore
has coverage `1.0`. This metric describes ingestion execution coverage; it does
not claim that the provider contains every historical observation or that a
stored financial value is economically correct.

Provider-specific row validation remains inside dataset services. A later
historical coverage/continuity layer can assess date-range completeness without
coupling that concern to ingestion execution accounting.

Ingestion runs also support an optional caller-supplied idempotency key. For a
given dataset, reusing the same key returns the previously completed run
summary instead of executing the dataset again. QuantCore stores a request
fingerprint with the run so accidental reuse of a key for different inputs is
rejected. A key that is already running is also rejected rather than creating
concurrent duplicate work. Callers that intentionally want a new execution
should generate a new idempotency key.


Transient upstream/transport failures are retried with a bounded deterministic
policy (three attempts by default, with exponential backoff). Provider/input,
validation, and configuration failures are not retried. Each failed attempt is
rolled back before a retry so a partial transaction cannot leak into the next
attempt.

An ingestion process can also recover executions left in `RUNNING` after a
process crash. `recover_stale_runs` marks executions older than an explicit
operator-selected threshold as terminal failures. The original audit record
and idempotency key are retained; a subsequent execution must use a new
idempotency key rather than silently reusing an abandoned execution.

The market-wide scope is the **managed QuantCore universe**, currently the SEC
ticker/exchange feed filtered to the explicitly supported US listed-equity
exchanges. It must not be described as every US security until the instrument
taxonomy and source coverage are expanded.


## Financial statement temporal and filing identity

Financial statements are stored with explicit temporal semantics so research
queries do not have to infer whether an observation is annual, quarterly, TTM,
or instantaneous. The current foundation records:

- `fiscal_date`: the existing period-end date retained for API compatibility.
- `period_start`: start date when the source provides a duration period.
- `fiscal_year` and `fiscal_period`: provider-reported fiscal labels when available.
- `period_type`: `ANNUAL`, `QUARTERLY`, `TTM`, or `INSTANT`.
- `filing_date`, `filing_form`, and `accession_number`: filing identity when supplied by the source.

SEC CompanyFacts supplies the filing metadata used for SEC observations, with
`10-K`/`10-K/A` annual observations currently normalized as `ANNUAL` and
balance-sheet observations as `INSTANT`. FMP observations retain the same
canonical period model while only persisting filing fields when FMP supplies
them.

The uniqueness boundary is now `(company_id, fiscal_date, period_type)`,
which allows an annual and quarterly observation to coexist for the same
period-end date. Filing-revision history is intentionally not yet an event
log; that will be introduced with the later SEC filing/document layer.

## SEC filing metadata and filing events

SEC EDGAR submissions are the authoritative source for regulatory filing
identity and filing-event metadata. QuantCore uses the issuer CIK as the
lookup identity rather than resolving a filing through a potentially
ambiguous ticker.

The filing metadata layer stores, when supplied by SEC:

- accession number (the durable filing identity)
- filing date and report date
- EDGAR acceptance timestamp
- form, act, file number and film number
- filing items and primary document metadata
- XBRL / Inline XBRL flags
- fiscal year and fiscal period labels
- amendment classification
- canonical EDGAR filing URL

The submissions API exposes the current filing history and references
additional historical JSON files when older filings exist. QuantCore follows
those references so the filing metadata layer can backfill the available EDGAR
history without downloading the filing documents themselves.

Each persisted filing also receives a normalized lifecycle event. The current
event types are `FILED` and `AMENDED`; the event layer is intentionally
separate from filing identity so future corrections, removals, supersession
relationships and document-processing events can be added without changing
the filing's accession-number identity.


## Corporate actions foundation

QuantCore normalizes security-level dividends and stock splits into a durable
corporate-action dataset rather than relying on the presence of action columns
inside individual price rows. The normalized identity is
`(security_id, effective_date, action_type)`, with row-level provenance and
fetch time.

The current adapter derives these actions from Yahoo Finance historical price
history because Yahoo is the only configured historical market-data adapter
implemented in this repository. This is deliberately a **secondary research
source**, not the authoritative corporate-action source. The domain model and
provider contract are intentionally independent of Yahoo so a licensed or
primary
market-data provider can replace the adapter without changing the research
layer.

Only dividends and stock splits are modeled in this increment. Mergers,
acquisitions, spinoffs, tender offers, symbol changes and delistings are not
treated as dividends/splits and are deliberately deferred to a later
security-lifecycle/corporate-action expansion.


## SEC XBRL Fact Observations

SEC EDGAR CompanyFacts is the authoritative source for the raw XBRL fact observation layer. QuantCore preserves observations by accession number rather than collapsing later filings or amendments into the earlier observation. The curated income statement, balance sheet, and cash-flow layers remain projections above this observation layer.


## Macro / economic data foundation

QuantCore uses FRED as the primary macroeconomic data provider. The FRED web
services API also exposes ALFRED real-time-period/vintage semantics, allowing
QuantCore to request a series as it was known on a historical date rather than
only retrieving today's revised value. The API requires a FRED API key.

The macro layer is intentionally independent of the security/company ingestion
scope. A macro series is identified by `(source, series_id)`, while each
observation is identified by `(series_id, observation_date, vintage_date)`.
This preserves multiple revisions of the same economic observation.

The first foundation stores FRED series metadata and vintage snapshots. It does
not yet claim complete historical vintage coverage for every series; a vintage
is present only after QuantCore has ingested that vintage. The existing
company/security ingestion orchestrator is deliberately not forced to treat a
macro series as a security. A later macro scheduling increment can add
macro-series freshness and market-wide macro refresh policies without changing
the domain model.

## Macro point-in-time and vintage semantics

Macro observations are treated as **vintage snapshots**, not mutable current
values. For a requested `as_of` date, QuantCore selects the latest **ingested**
vintage whose `vintage_date` is on or before that date, independently for each
observation date. A later revision can therefore never leak into an earlier
research date.

The FRED adapter requests an ALFRED real-time snapshot with
`realtime_start == realtime_end == vintage_date`. Row-level
`realtime_start`/`realtime_end` returned by FRED are preserved; the provider
rejects an observation whose real-time interval does not contain the requested
vintage. The requested vintage itself is also persisted, so multiple revisions
of the same observation remain distinct rows.

An `as_of` query is therefore **look-ahead safe**, but it is only an exact
historical reconstruction when that vintage has actually been ingested.
The API exposes `require_exact_vintage=true` when callers need to fail rather
than silently use the most recent earlier ingested snapshot.

This distinction is important: ingestion freshness tells us when QuantCore last
checked the provider; vintage coverage tells us which historical information
sets QuantCore can actually reconstruct. One must not be used as a substitute
for the other.

## Macro ingestion scheduling and freshness

Macro ingestion is intentionally separate from the security/company ingestion
orchestrator. Macro series are scheduled by a series-oriented coordinator using
an explicit managed-series registry and per-series freshness windows.

The scheduler records last attempt, last successful ingestion, successful
vintage, record count, consecutive failures, and the last error. Freshness is
based on the successful ingestion timestamp; it does not claim that FRED data
is real-time or that every historical vintage has been captured.

The initial managed registry is deliberately small: `GDP`, `CPIAUCSL`,
`UNRATE`, `FEDFUNDS`, and `DGS10`. The registry is a scheduling boundary, not
a statement that these are the only useful FRED series.

The coordinator is synchronous and bounded. A future scheduler/worker can call
it without introducing Redis, Celery, Kafka, or other infrastructure into the
domain layer.


## Market price observation semantics

QuantCore stores historical market prices with explicit adjustment semantics.
The canonical price row keeps the provider-reported OHLC fields on an explicit
`price_basis` and may also retain a separate `adjusted_close`. The Yahoo
adapter requests `auto_adjust=False` and `actions=True`, so `open`, `high`,
`low`, and `close` are intentionally the provider's unadjusted OHLC fields,
while `adjusted_close` is preserved separately for return-oriented research.
Corporate actions remain a separate normalized dataset and are not inferred
solely from adjusted prices.

The current historical price implementation is EOD-oriented and sourced from
Yahoo as a secondary research source. A future primary/licensed market-data
adapter must preserve the same canonical semantics rather than silently
changing the meaning of `close`. Intraday timestamps, additional bar
frequencies, and real-time feeds remain separate future layers.

## Market price reconciliation and point-in-time semantics

Market prices are treated as observations that can be corrected by the upstream
provider after initial ingestion. The canonical `prices` row represents the
latest known value, while `price_observation_revisions` preserves immutable
snapshots of values that QuantCore observed at each revision point.

A revision is created only when the market observation itself changes. Repeated
fetches of an unchanged observation do not create artificial revisions and do
not move its knowledge timestamp. This keeps revision history meaningful while
still allowing provider corrections to be audited.

The market observation date (`prices.date`) and the knowledge timestamp
(`price_observation_revisions.known_at`) have different meanings. The former is
when the market observation occurred; the latter is when QuantCore knew that
specific version of the observation. PIT queries select, independently for each
market date, the latest revision whose `known_at` is on or before the requested
`as_of` timestamp.

The API therefore supports both the current corrected history and a historical
knowledge-set reconstruction through `GET /prices/{symbol}?as_of=...`. An
`as_of` result is only exact for revisions that have actually been ingested by
QuantCore; ingestion freshness does not imply complete historical revision
coverage.


## Point-in-time market analytics boundary

Derived market analytics must use the same point-in-time price semantics as the
underlying market observations. The analytics service therefore accepts an
optional `as_of` timestamp. Without `as_of`, analytics use the current canonical
price history; with `as_of`, the service selects the latest price revision
known at that timestamp before calculating the indicator. This prevents a
corrected market price that was learned later from silently entering a
historical indicator calculation. The indicator formulas themselves remain
pure computations over the selected price series; this increment does not add
new indicators or alter their mathematical definitions.


## Financial statement reconciliation and point-in-time semantics

Normalized income statements, balance sheets, and cash-flow statements are
treated as observations that may be corrected by an upstream provider after
initial ingestion. The canonical statement row remains the latest known value,
while `financial_statement_revisions` preserves immutable snapshots for each
revision. Repeated ingestion of an unchanged statement does not create a new
revision. A changed observation creates the next revision and updates the
canonical row atomically.

Each revision records `known_at`, which represents when QuantCore learned that
specific normalized statement version. The fiscal date and filing date retain
the market/reporting-period semantics and are not substituted for the
knowledge timestamp. PIT reads select the latest ingested revision for each
statement period whose `known_at` is on or before the requested `as_of`
time. Historical PIT reconstruction is therefore exact only for revisions that
QuantCore has actually ingested. Existing rows backfilled by the migration
provide a baseline revision at their recorded `fetched_at` when available;
they do not manufacture historical knowledge timestamps.

The statement APIs expose the optional `as_of` query parameter for income
statements, balance sheets, and cash-flow statements. Sync responses also
report created, updated, unchanged, and processed counts so reconciliation is
observable rather than silently treating every existing row as immutable.

## Corporate action reconciliation and point-in-time semantics

Corporate actions are treated as security-level observations that can be corrected by the upstream provider after initial ingestion. The canonical corporate-action row represents the latest known value, while `corporate_action_revisions` preserves immutable snapshots at each revision point.

Repeated ingestion of an unchanged action does not create a new revision. A changed amount or split ratio updates the canonical action and creates the next revision with a `known_at` timestamp. Existing actions backfilled by the migration receive a baseline revision at their recorded `fetched_at` when available.

The corporate-action API supports an optional `as_of` timestamp. PIT reads select the latest ingested revision for each action known at or before that timestamp. As with other QuantCore PIT datasets, this reconstructs the knowledge set represented by ingested revisions; it does not manufacture provider history that QuantCore never captured.


## Cross-dataset point-in-time alignment

QuantCore now provides a shared PIT alignment boundary across the existing
market-price, financial-statement, corporate-action, SEC XBRL, and macro
stores. `PITAlignmentService` does not duplicate or rewrite dataset-specific
selection logic; it resolves the canonical security/company identity and
invokes each dataset's existing PIT repository under the same requested
`as_of` timestamp.

The resulting `PITAlignedSnapshot` is an in-memory research boundary rather
than a new persisted dataset. This keeps the first cross-dataset increment
focused on temporal correctness and composition before introducing feature
tables, research observations, or backtest-specific schemas.

Market prices, financial statements, and corporate actions use their immutable
revision `known_at` timestamps. SEC XBRL timestamp selection uses
`accepted_at` when available and falls back to the filing date for legacy
observations that do not have an accepted timestamp. This avoids treating a
later same-day SEC acceptance as known before its actual acceptance time.

Macro observations currently have calendar-date vintage semantics rather than
an intraday release timestamp. Cross-dataset alignment therefore maps the
shared `as_of` timestamp to its calendar date when selecting macro vintages.
This is intentionally explicit: macro PIT is date-granular until release-time
metadata is introduced, and the alignment layer must not imply finer temporal
precision than the underlying source supports.

The snapshot is exact only with respect to historical observations and
revisions actually ingested by QuantCore. Missing historical ingestion is not
filled by the alignment layer and must remain distinguishable from a value
that was known at the requested timestamp.

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

`ResearchStrategyDefinition` establishes the first Phase III contract above the research-signal
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
semantics, or persistence; those belong to subsequent Phase III boundaries.

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


## Historical coverage and continuity

Execution completeness and historical coverage are separate guarantees.
`IngestionQualityService` answers whether an ingestion run covered its
eligible targets; `HistoricalCoverageService` answers whether a requested
historical interval contains the observations that a dataset-specific
schedule says should exist.

The coverage service is intentionally schedule-driven. It does **not** assume
that every calendar day is an observation day. The caller supplies the
expected observation schedule, such as an exchange trading calendar for EOD
prices or a dataset-specific publication schedule for fundamentals.

For a requested interval it deterministically reports:

- expected observation count,
- observed observation count,
- missing observation count,
- coverage ratio,
- first and last observed timestamps,
- exact missing timestamps,
- number of distinct missing runs, and
- largest consecutive missing run.

The service rejects duplicate timestamps, naive timestamps, and observations
outside the requested interval. It does not silently discard unexpected
observations or reinterpret weekends and holidays as missing data.

Coverage states are:

- `COMPLETE`: every expected observation is present.
- `PARTIAL`: some, but not all, expected observations are present.
- `NO_OBSERVATIONS`: the schedule expects observations but none were observed.
- `NO_EXPECTED_OBSERVATIONS`: the supplied schedule contains no observations;
  this is not treated as complete coverage.

This boundary is deliberately read-only and provider-neutral. Dataset adapters
and repositories remain responsible for obtaining observations; market
calendar and publication-calendar logic remains outside the generic coverage
service. Research and backtesting consumers can therefore require an explicit
coverage result before treating a historical interval as usable.


## Ingestion lineage and provenance

`IngestionLineage` provides the execution-level bridge between the ingestion coordinator
and the company/security entity whose data was successfully persisted. Each successful
entity-level ingestion records the coordinator run, dataset, entity scope and identity,
provider source, processed-record count, and timestamp.

This complements the existing row-level provenance fields (`source`, `fetched_at`, and
`source_reference`) rather than replacing them. The lineage record answers **which
ingestion execution produced this entity's persisted dataset**, while dataset-specific
rows retain their more precise source references where available.

Only successful entity ingestion is recorded as a lineage edge. Freshness skips are not
new data production events, and failed attempts remain represented by the ingestion run
and failure/health state rather than being presented as successful provenance.

The lineage identity is deterministic within an execution: a run can have at most one
lineage record for a given company or security. Historical runs are retained, so an
entity can be traced across successive ingestion executions without overwriting the
execution history.

This is execution-level lineage, not yet a universal row-to-row dependency graph.
Research observations continue to carry their own input manifest and fingerprint, while
source datasets retain their existing provenance. Future experiment and evidence layers
can use these identifiers to build higher-level research lineage without coupling the
ingestion coordinator to every downstream calculation.

## Scheduled Ingestion / Job Triggering

QuantCore persists ingestion schedules separately from ingestion execution. A schedule defines a dataset request, interval, next due time, and enabled state. `IngestionScheduleService.trigger_due()` converts due schedules into persistent `ingestion_jobs` without executing provider work itself.

The scheduled timestamp is incorporated into the generated job idempotency key. Schedule advancement and job creation occur in the same database transaction, and missed intervals are coalesced rather than replayed as a burst. The trigger layer is therefore compatible with an external cron/systemd/Kubernetes scheduler without coupling the application to a scheduler framework.
