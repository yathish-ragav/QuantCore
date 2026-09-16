from __future__ import annotations

import argparse

from quantcore.core.production_data_policy import ProductionDataPolicy
from quantcore.db.database import SessionLocal
from quantcore.ingestion.datasets import IngestionDataset
from quantcore.services.ingestion_orchestrator import IngestionOrchestrator
from quantcore.services.universe_sync_service import UniverseSyncService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bootstrap bounded production US-equity data ingestion."
    )
    parser.add_argument(
        "--datasets",
        nargs="+",
        choices=[dataset.value for dataset in IngestionDataset],
        default=[
            IngestionDataset.COMPANY.value,
            IngestionDataset.PRICE_HISTORY.value,
            IngestionDataset.CORPORATE_ACTIONS.value,
            IngestionDataset.SEC_FILINGS.value,
            IngestionDataset.SEC_XBRL_FACTS.value,
        ],
        help="Datasets to ingest after the SEC universe sync.",
    )
    parser.add_argument(
        "--symbols",
        nargs="+",
        help="Explicit symbols to ingest. Overrides --limit.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Maximum number of active securities to ingest.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Refresh fresh datasets too; default is stale-only.",
    )
    parser.add_argument(
        "--skip-universe",
        action="store_true",
        help="Skip the SEC universe synchronization.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    ProductionDataPolicy.validate_all()

    if not args.symbols and args.limit is None and not args.skip_universe:
        # Universe-only bootstrap is safe without a bounded market-data target.
        pass
    elif not args.symbols and args.limit is None:
        raise SystemExit(
            "Provide --symbols or --limit for dataset ingestion."
        )

    db = SessionLocal()
    try:
        if not args.skip_universe:
            print("Synchronizing the SEC issuer/security universe...")
            processed = UniverseSyncService(db).sync()
            print(f"SEC universe synchronization complete: {processed} records processed.")

        if not args.skip_universe and not args.symbols and args.limit is None:
            return

        datasets = [IngestionDataset(value) for value in args.datasets]
        results = IngestionOrchestrator(db).sync_market(
            datasets=datasets,
            symbols=args.symbols,
            limit=args.limit,
            only_stale=not args.all,
        )

        for result in results:
            print(
                f"{result.dataset.value}: "
                f"eligible={result.eligible} "
                f"attempted={result.attempted} "
                f"succeeded={result.succeeded} "
                f"skipped={result.skipped} "
                f"failed={result.failed}"
            )
            for error in result.errors:
                print(f"  ERROR: {error}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
