from backend.app.db.database import Base, engine
from backend.app import models

print(Base.metadata.tables.keys())
Base.metadata.create_all(bind=engine)
