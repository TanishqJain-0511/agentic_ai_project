from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector

from backend.app.db.database import Base

# Embedding dimension for BAAI/bge-small-en-v1.5
EMBEDDING_DIM = 384


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String, nullable=False, index=True)    # e.g. "SEBI_circular_2024.pdf"
    chunk_index = Column(Integer, nullable=False)          # position within the source doc
    content = Column(Text, nullable=False)                 # raw chunk text
    embedding = Column(Vector(EMBEDDING_DIM), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
