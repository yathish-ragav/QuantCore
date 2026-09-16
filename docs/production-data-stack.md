# Production Data Stack

Phase XI establishes the production source policy for QUANTCORE's public US-equity
research product.

## Source roles

| Domain | Production source | Reason | Commercial/display requirement |
|---|---|---|---|
| Issuer universe / CIK / EDGAR identity | SEC EDGAR | Government source of filing and issuer data | Follow SEC fair-access policy and identify the application with a valid User-Agent |
| Filings / XBRL fundamentals | SEC EDGAR APIs | Primary regulatory source | Follow SEC access policy; retain filing/accession provenance |
| EOD/intraday market data | Massive business/enterprise entitlement | Customer-facing commercial market-data rights are required | A commercial/display entitlement is required before production use |
| Corporate actions (market-data events) | Massive business/enterprise entitlement | Structured splits/dividends feed | Same market-data licensing boundary |
| News | Massive news endpoint under the applicable commercial entitlement | Provider supplies article metadata and source links | Verify the selected plan/add-on permits the intended customer-facing use |
| Macro | FRED | Public macroeconomic source | Observe the applicable FRED terms/attribution requirements |
| Index membership | Licensed index provider | S&P DJI / Nasdaq / FTSE Russell data are licensed datasets | Entitlement must be recorded in the index-source licensing tables |

SEC publishes ticker/CIK/exchange associations and REST APIs for submissions and
XBRL data. Automated access must comply with SEC fair-access controls; QUANTCORE
therefore uses a configurable identifying User-Agent and does not implement
unbounded crawling.

For market data, QUANTCORE does **not** treat Yahoo Finance or a personal-use
market-data subscription as a production entitlement. The production policy
requires Massive for market/realtime data and a production key. The application
must be configured with the commercial rights that match the intended
customer-facing use before enabling production ingestion.

## Production configuration

Production should use:

```text
MARKET_DATA_PROVIDER=massive
REALTIME_MARKET_DATA_PROVIDER=massive
FINANCIAL_DATA_PROVIDER=sec
REGULATORY_DATA_PROVIDER=sec
MACRO_DATA_PROVIDER=fred
MASSIVE_API_KEY=<commercially entitled key>
SEC_USER_AGENT=QuantCore/<version> contact:<operational contact>
PRODUCTION_DATA_POLICY_ENFORCED=true
```

Development can continue to use existing provider adapters for testing, but those
providers must not silently become the public production data source.

## Historical data policy

A successful API response is not itself proof of historical completeness.

For each dataset QUANTCORE records:

- source/provider,
- fetch timestamp,
- source reference/request identity where available,
- canonical observation identity,
- immutable revision when the provider corrects an observation,
- point-in-time knowledge timestamp where the source semantics support it,
- ingestion execution lineage,
- freshness and coverage state.

Historical research may only claim the coverage actually present in the database.

## First production bootstrap

The repository includes `scripts/bootstrap_production_data.py`. It:

1. synchronizes the SEC company/security universe;
2. verifies the production provider policy;
3. runs a bounded set of configured datasets through the existing durable ingestion
   orchestrator.

It intentionally requires an explicit `--limit` or `--symbols` for broad dataset
ingestion so a first deployment cannot accidentally generate an unbounded provider
bill or SEC request burst.

Start with a small pilot:

```bash
cd ~/Developer/QuantCore/backend
source .venv/bin/activate

python ../scripts/bootstrap_production_data.py   --limit 25   --datasets company price_history corporate_actions news   --all
```

After the pilot passes data-quality review, increase the limit in controlled batches.

Do not use the script to ingest an index such as the S&P 500 from a public webpage.
Index membership remains behind the licensed index-data ingestion contract created
in Phase IX.


## Legacy company enrichment provenance

Company identity is authoritative from SEC. Optional enrichment fields may be
absent when the configured provider does not publish them. Empty-string
placeholders are not used for new universe records; missing enrichment is stored
as `NULL`. Existing pre-provenance enrichment values that cannot be attributed to
a known provider are migrated to the explicit `UNKNOWN` provenance source. A
subsequent authoritative provider may replace `UNKNOWN` ownership and establish
known provenance. QuantCore never fabricates a sector or other classification to
fill a provider omission.
