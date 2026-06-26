from sqlalchemy import text

from backend.app.db.database import Base, engine
from backend.app import models  # noqa: F401 — ensures all models are registered


async def init_db():
    async with engine.begin() as conn:
        # Enable pgvector extension (idempotent — safe to run on every startup)
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
