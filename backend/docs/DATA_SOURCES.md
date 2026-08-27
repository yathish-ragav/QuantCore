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
