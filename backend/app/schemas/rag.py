from pydantic import BaseModel, Field
from typing import List


class RAGIngestRequest(BaseModel):
    source: str = Field(..., description="Document name or identifier, e.g. 'SEBI_circular_2024'")
    content: str = Field(..., min_length=10, description="Full document text to chunk and embed")
    chunk_size: int = Field(default=800, ge=100, le=2000)
    chunk_overlap: int = Field(default=100, ge=0, le=500)


class RAGIngestResponse(BaseModel):
    source: str
    chunks_stored: int
    message: str


class RAGRetrieveRequest(BaseModel):
    query: str = Field(..., min_length=3, description="Natural language query")
    top_k: int = Field(default=3, ge=1, le=10)
    source_filter: str | None = Field(default=None, description="Limit search to a specific source")


class RetrievedChunk(BaseModel):
    source: str
    chunk_index: int
    content: str
    similarity: float    # cosine similarity score (0–1, higher is better)


class RAGRetrieveResponse(BaseModel):
    query: str
    results: List[RetrievedChunk]
