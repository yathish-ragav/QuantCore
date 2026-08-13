from quantcore.db.database import SessionLocal
from quantcore.universe.service import UniverseService


def main() -> None:
    db = SessionLocal()

    try:
        service = UniverseService(db)

        print("Starting SEC universe synchronization...")

        synced = service.sync()

        print(
            f"Universe synchronization complete. "
            f"Securities processed: {synced}"
        )

    except Exception:
        print("Universe synchronization failed.")
        raise

    finally:
        db.close()


if __name__ == "__main__":
    main()