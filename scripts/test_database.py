from sqlalchemy import text

from quantcore.db.database import engine

with engine.connect() as conn:
    result = conn.execute(text("SELECT version();"))

    print("\nConnected Successfully!\n")

    print(result.fetchone()[0])