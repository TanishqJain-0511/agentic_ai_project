"""
RAG (Retrieval-Augmented Generation) Service — Phase 11

Handles:
  - Document ingestion: text → chunks → embeddings → pgvector store
  - Retrieval: query → embedding → cosine similarity search → top-k chunks
  - Generation: retrieved chunks → Ollama prompt → grounded answer

Embedding model: BAAI/bge-small-en-v1.5 (384-dim, runs fully locally via sentence-transformers)
Vector store:    PostgreSQL + pgvector (cosine distance)
LLM:             Ollama llama3.2:3b (answers grounded strictly in retrieved context)
"""

from typing import List
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.models.document_chunk import DocumentChunk, EMBEDDING_DIM
from backend.app.schemas.rag import (
    RAGIngestRequest,
    RAGIngestResponse,
    RAGRetrieveRequest,
    RAGRetrieveResponse,
    RAGGenerateRequest,
    RAGGenerateResponse,
    RetrievedChunk,
)

_EMBEDDING_MODEL_NAME = "BAAI/bge-small-en-v1.5"
_model = None  # lazy-loaded on first use


def _get_embedding_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(_EMBEDDING_MODEL_NAME)
    return _model


def _embed(texts: List[str]) -> List[List[float]]:
    model = _get_embedding_model()
    embeddings = model.encode(texts, normalize_embeddings=True)
    return embeddings.tolist()


def _chunk_text(text: str, chunk_size: int, overlap: int) -> List[str]:
    """Simple character-based sliding window chunker."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end].strip())
        if end >= len(text):
            break
        start += chunk_size - overlap
    return [c for c in chunks if c]


# ── Ingest ────────────────────────────────────────────────────────────────────

async def ingest_document(db: AsyncSession, data: RAGIngestRequest) -> RAGIngestResponse:
    chunks = _chunk_text(data.content, data.chunk_size, data.chunk_overlap)
    if not chunks:
        return RAGIngestResponse(source=data.source, chunks_stored=0, message="No content to ingest.")

    embeddings = _embed(chunks)

    # Delete existing chunks for this source to allow re-ingestion
    await db.execute(
        text("DELETE FROM document_chunks WHERE source = :source"),
        {"source": data.source},
    )

    for idx, (chunk_text, embedding) in enumerate(zip(chunks, embeddings)):
        db.add(DocumentChunk(
            source=data.source,
            chunk_index=idx,
            content=chunk_text,
            embedding=embedding,
        ))

    await db.commit()

    return RAGIngestResponse(
        source=data.source,
        chunks_stored=len(chunks),
        message=f"Ingested {len(chunks)} chunks from '{data.source}'.",
    )


# ── Retrieve ──────────────────────────────────────────────────────────────────

async def retrieve_chunks(db: AsyncSession, data: RAGRetrieveRequest) -> RAGRetrieveResponse:
    query_embedding = _embed([data.query])[0]

    # pgvector cosine distance operator: <=>
    # 1 - cosine_distance = cosine_similarity
    embedding_col = "embedding"
    distance_expr = f"{embedding_col} <=> CAST(:embedding AS vector({EMBEDDING_DIM}))"

    sql = f"""
        SELECT source, chunk_index, content,
               1 - ({distance_expr}) AS similarity
        FROM document_chunks
        {"WHERE source = :source_filter" if data.source_filter else ""}
        ORDER BY {distance_expr}
        LIMIT :top_k
    """

    params: dict = {
        "embedding": str(query_embedding),
        "top_k": data.top_k,
    }
    if data.source_filter:
        params["source_filter"] = data.source_filter

    rows = await db.execute(text(sql), params)
    results = rows.fetchall()

    return RAGRetrieveResponse(
        query=data.query,
        results=[
            RetrievedChunk(
                source=row.source,
                chunk_index=row.chunk_index,
                content=row.content,
                similarity=round(float(row.similarity), 4),
            )
            for row in results
        ],
    )


# ── Generate ──────────────────────────────────────────────────────────────────

_RAG_SYSTEM_PROMPT = """You are a precise financial document assistant.
Answer the user's question using ONLY the context passages provided below.
If the answer is not present in the context, say "I could not find this information in the provided documents."
Do not use any outside knowledge. Be concise and factual."""


async def generate_rag_answer(db: AsyncSession, data: RAGGenerateRequest) -> RAGGenerateResponse:
    # Step 1: retrieve relevant chunks
    retrieve_req = RAGRetrieveRequest(
        query=data.query,
        top_k=data.top_k,
        source_filter=data.source_filter,
    )
    retrieved = await retrieve_chunks(db, retrieve_req)

    if not retrieved.results:
        return RAGGenerateResponse(
            query=data.query,
            answer="No relevant documents found. Please ingest documents first.",
            sources_used=[],
            status="no_chunks_found",
        )

    # Step 2: build context block from retrieved chunks
    context_block = "\n\n---\n\n".join(
        f"[Source: {r.source}, chunk {r.chunk_index}]\n{r.content}"
        for r in retrieved.results
    )
    sources_used = [f"{r.source}#chunk{r.chunk_index}" for r in retrieved.results]

    user_prompt = f"Context:\n{context_block}\n\nQuestion: {data.query}"

    # Step 3: call Ollama
    try:
        from langchain_ollama import ChatOllama
        from langchain_core.messages import HumanMessage, SystemMessage
        from backend.app.config import settings

        llm = ChatOllama(model="llama3.2:3b", base_url=settings.OLLAMA_HOST)
        response = await llm.ainvoke([
            SystemMessage(content=_RAG_SYSTEM_PROMPT),
            HumanMessage(content=user_prompt),
        ])

        return RAGGenerateResponse(
            query=data.query,
            answer=response.content.strip(),
            sources_used=sources_used,
            status="success",
        )

    except Exception as e:
        error_str = str(e).lower()
        if "connection" in error_str or "refused" in error_str or "connect" in error_str:
            return RAGGenerateResponse(
                query=data.query,
                answer="Ollama is not running. Start it with: ollama serve && ollama pull llama3.2:3b",
                sources_used=sources_used,
                status="ollama_unavailable",
            )
        return RAGGenerateResponse(
            query=data.query,
            answer=f"Generation failed: {e}",
            sources_used=sources_used,
            status="error",
        )
