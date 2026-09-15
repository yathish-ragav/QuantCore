import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"


def main() -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(BACKEND / "src") + os.pathsep + env.get("PYTHONPATH", "")

    subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"],
        cwd=BACKEND,
        env=env,
        check=True,
    )

    from quantcore.db.database import SessionLocal
    from quantcore.services.universe_sync_service import UniverseSyncService

    db = SessionLocal()
    try:
        processed = UniverseSyncService(db).sync()
        print(f"Security universe bootstrap complete. Securities processed: {processed}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
