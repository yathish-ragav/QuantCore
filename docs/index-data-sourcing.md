# QuantCore index data sourcing and licensing policy

QuantCore must not scrape, bundle, or redistribute index constituent history merely because a provider publishes a public-facing page. Index methodology, constituent, weighting, corporate-action, and historical datasets can be licensed intellectual property.

## Authoritative-source policy

| Index family | Authoritative source | Historical constituent source | QuantCore status |
| --- | --- | --- | --- |
| S&P branded indexes | S&P Dow Jones Indices | Licensed S&P DJI constituent/data package | Do not ingest until an applicable license is documented |
| Nasdaq indexes | Nasdaq Global Indexes / GIW | Licensed GIW/API/feed or approved redistributor | Do not ingest until an applicable license is documented |
| Russell / FTSE Russell indexes | FTSE Russell / LSEG | Licensed historical constituent/weight package | Do not ingest until an applicable license is documented |

The implementation records the operational licensing decision in `market_index_data_sources`. A source must be explicitly marked `AUTHORIZED` with `storage_allowed=true` before membership data can be persisted through the import service.

## Why public web pages are not treated as a feed

Public index pages can establish what an index provider publishes and can provide methodology/context, but they do not automatically grant QuantCore rights to copy, store, display, or redistribute the underlying historical constituent dataset. The production ingestion path therefore requires an entitled feed/file and a recorded license decision.

## Required source record

Before importing a production index dataset, register a source with:

- provider and dataset name;
- authority classification;
- license status;
- storage permission;
- display permission;
- redistribution permission;
- terms/agreement reference;
- attribution requirements;
- review and expiry dates.

## Canonical import contract

The importer accepts a canonical, already-mapped CSV containing:

```text
security_id,effective_from,effective_to,weight,known_at,source_reference
```

`security_id` is the QuantCore security-master identity. The mapping from provider identifiers (CUSIP, ISIN, vendor security ID, ticker/exchange, etc.) to QuantCore securities must occur in the source-specific mapping stage before this persistence boundary.

Every imported membership row retains `known_at` separately from its effective membership dates. This is required for point-in-time research and late corrections.

## Maintenance model

Loads are append-only and fingerprinted. Re-running an identical source file is idempotent. New source knowledge can create a new membership revision rather than overwriting the earlier known state.

QuantCore must not mark a source as authorized based on an assumption that a provider's public website permits redistribution. The agreement or provider terms remain the source of truth.
