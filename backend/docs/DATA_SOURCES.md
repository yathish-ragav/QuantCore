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
