import argparse
import csv
from datetime import date, datetime, timezone
from decimal import Decimal

from quantcore.db.database import SessionLocal
from quantcore.services.market_index_import_service import (
    IndexMembershipImportRow,
    MarketIndexImportService,
)


def _optional_date(value: str) -> date | None:
    value = value.strip()
    return date.fromisoformat(value) if value else None


def _required_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import canonical, licensed index membership history into QuantCore."
    )
    parser.add_argument("--index", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--file", required=True)
    args = parser.parse_args()

    rows = []
    with open(args.file, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        required = {"security_id", "effective_from", "known_at"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise SystemExit(
                "Missing required columns: " + ", ".join(sorted(missing))
            )

        for line_number, row in enumerate(reader, start=2):
            try:
                rows.append(
                    IndexMembershipImportRow(
                        security_id=int(row["security_id"]),
                        effective_from=date.fromisoformat(row["effective_from"].strip()),
                        effective_to=_optional_date(row.get("effective_to", "")),
                        weight=(
                            Decimal(row["weight"].strip())
                            if row.get("weight", "").strip()
                            else None
                        ),
                        known_at=_required_datetime(row["known_at"]),
                        source_reference=(row.get("source_reference") or None),
                    )
                )
            except (TypeError, ValueError) as exc:
                raise SystemExit(f"Invalid row {line_number}: {exc}") from exc

    db = SessionLocal()
    try:
        imported = MarketIndexImportService(db).import_rows(
            index_key=args.index,
            source_key=args.source,
            rows=rows,
        )
        print(f"Index membership import complete. Records imported: {imported}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
