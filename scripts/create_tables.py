from quantcore.db.database import Base, engine

import quantcore.models

print("Creating tables...")

Base.metadata.create_all(bind=engine)

print("Done.")