from backend.app.db.database import Base, engine

Base.metadata.create_all(bind=engine)
