from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from quantcore.db.database import SessionLocal
from quantcore.universe.audit import audit
from quantcore.universe.providers.massive import MassiveUniverseProvider


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Audit active SEC securities against Massive's active stock reference "
            "universe without modifying the database."
        )
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional JSON output path. Defaults to data/audits/<timestamp>.json.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    output = args.output or (
        Path("data/audits")
        / f"security-classification-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}.json"
    )

    db = SessionLocal()
    try:
        report = audit(db, MassiveUniverseProvider())
    finally:
        db.close()

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")

    print(json.dumps(report["summary"], indent=2, sort_keys=True))
    print("\nUNKNOWN BY PROVIDER TYPE")
    print(json.dumps(report["unknown"]["by_provider_type"], indent=2, sort_keys=True))
    print("\nUNMATCHED BY REASON")
    print(json.dumps(report["unmatched"]["by_reason"], indent=2, sort_keys=True))
    print(f"\nAudit written to {output}")


if __name__ == "__main__":
    main()
