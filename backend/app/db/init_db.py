from backend.app.db.database import Base, engine
from backend.app import models

Base.metadata.create_all(bind=engine)
