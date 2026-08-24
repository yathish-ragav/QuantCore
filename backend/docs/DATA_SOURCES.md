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
