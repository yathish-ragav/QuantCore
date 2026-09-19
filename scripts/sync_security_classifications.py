from __future__ import annotations

import json

from quantcore.db.database import SessionLocal
from quantcore.services.security_classification_service import (
    SecurityClassificationService,
)


def main() -> None:
    db = SessionLocal()
    try:
        result = SecurityClassificationService(db).sync()
        print(
            json.dumps(
                {
                    "eligible": result.eligible,
                    "classified": result.classified,
                    "unknown": result.unknown,
                    "unmatched": result.unmatched,
                },
                indent=2,
                sort_keys=True,
            )
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
