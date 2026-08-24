import argparse

from quantcore.db.database import SessionLocal
from quantcore.ingestion.datasets import IngestionDataset
from quantcore.services.ingestion_orchestrator import IngestionOrchestrator


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run bounded QuantCore market-wide dataset ingestion."
    )
    parser.add_argument(
        "--datasets",
        nargs="+",
        choices=[dataset.value for dataset in IngestionDataset],
        default=[dataset.value for dataset in IngestionDataset],
        help="Datasets to ingest. Defaults to every registered dataset.",
    )
    parser.add_argument(
        "--symbols",
        nargs="+",
        help="Optional symbols to restrict the run to.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Maximum number of active securities to inspect.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Refresh fresh datasets too; default is stale-only.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    datasets = [
        IngestionDataset(dataset)
        for dataset in args.datasets
    ]

    db = SessionLocal()

    try:
        results = IngestionOrchestrator(db).sync_market(
            datasets=datasets,
            symbols=args.symbols,
            limit=args.limit,
            only_stale=not args.all,
        )

        for result in results:
            print(
                f"{result.dataset.value}: "
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
