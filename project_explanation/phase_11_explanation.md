# Phase 11 — RAG Knowledge Base: Full Deep Dive

---

## What is this phase doing conceptually?

All phases so far compute with structured data: numbers in database columns, fixed questionnaire answers, JSON fields. 
Phase 11 introduces **unstructured text** — the ability to store and semantically search through 
documents like SEBI circulars, AMC fact sheets, or financial education content.

RAG stands for **Retrieval-Augmented Generation**. The pattern:
1. **Ingest**: split a document into chunks, embed each chunk as a vector, store in a vector database
2. **Retrieve**: embed a query, find the chunks most semantically similar to it via cosine similarity
3. **Generate**: (future) pass the retrieved chunks as context to the LLM to answer the query

Phase 11 implements steps 1 and 2. Step 3 (generation) is Phase 12's domain.

---

## Why RAG? Why not just stuff everything into the LLM prompt?

LLMs have context window limits (e.g., 8K tokens for `llama3.2:3b`). A SEBI circular can be 50 pages. 
You can't fit it all in the prompt. RAG solves this by only retrieving the **relevant chunks** 
(typically 3–5 out of hundreds) and injecting just those into the prompt.

More importantly, RAG grounds the LLM's answers in real documents. 
Without RAG, the LLM hallucinates financial regulations. With RAG, it reads the actual rule text and cites it.

---

## The Architecture

```
POST /rag/ingest:
  text → chunk_text() → _embed() → DocumentChunk ORM → PostgreSQL (pgvector)

POST /rag/retrieve:
  query → _embed() → cosine similarity SQL → top-k DocumentChunks
```

Three key technologies:
- **pgvector** — PostgreSQL extension for storing and querying vectors (embeddings)
- **BAAI/bge-small-en-v1.5** — the embedding model (384-dimensional, runs locally)
- **sentence-transformers** — Python library that runs the embedding model

---

## Concept 1: What is an Embedding?

An embedding is a vector (list of floats) that represents the **semantic meaning** of a piece of text. 
Similar texts have similar vectors (small cosine distance). Unrelated texts have dissimilar vectors.

```
"What is the SIP investment limit?" → [0.12, -0.34, 0.78, 0.01, ..., 0.55]  (384 dims)
"Monthly SIP cap rules"            → [0.14, -0.31, 0.76, 0.03, ..., 0.52]  (nearby!)
"Recipe for chocolate cake"        → [0.89,  0.22, -0.41, 0.67, ..., -0.11] (far away)
```

`BAAI/bge-small-en-v1.5` is a 384-dimensional model. Each chunk becomes a 384-float vector. 
These vectors are stored in PostgreSQL via pgvector.

**Why 384 dimensions?** The model was trained to produce 384-dim vectors. 
Larger models (like `e5-base`, 768-dim) give more nuanced representations but are slower. 
384-dim is a good balance for a local, zero-cost deployment.

---

## Concept 2: pgvector

pgvector is a PostgreSQL extension that adds:
1. A `vector(n)` column type — stores a list of n floats
2. Vector distance operators: `<=>` (cosine), `<->` (L2/Euclidean), `<#>` (inner product)
3. Vector indexes (IVFFlat, HNSW) for fast approximate nearest-neighbour search

Without pgvector, you'd need a separate vector database (Pinecone, Weaviate, Qdrant). 
With pgvector, your existing PostgreSQL handles both structured data and vector search — fewer infrastructure components.

### Enabling pgvector

```python
# init_db.py
await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
```

Run once at startup (idempotent). The docker-compose.yml uses `pgvector/pgvector:pg17` instead of `postgres:17` — this is the official pgvector Docker image that has the extension pre-installed.

---

## Concept 3: DocumentChunk Model

```python
class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id          = Column(Integer, primary_key=True, index=True)
    source      = Column(String, nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)
    content     = Column(Text, nullable=False)
    embedding   = Column(Vector(EMBEDDING_DIM), nullable=True)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())
```

`Vector(EMBEDDING_DIM)` — from `pgvector.sqlalchemy`, maps to PostgreSQL's `vector(384)` column type.

`source` — identifies which document this chunk came from (e.g., `"SEBI_circular_2024.pdf"`). Indexed for fast filtering when retrieving only from a specific source.

`chunk_index` — position within the source document. Not used for retrieval, but useful for debugging (chunk 0 = first 800 chars, chunk 1 = next 700, etc.).

`content` — the raw text of the chunk. The LLM reads this text when generating answers.

`embedding` is `nullable=True` — theoretically a chunk could exist without an embedding (e.g., if the embedding model failed). In practice, we always embed before storing.

---

## Concept 4: Chunking Strategy

```python
def _chunk_text(text: str, chunk_size: int, overlap: int) -> List[str]:
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end].strip())
        if end >= len(text):
            break
        start += chunk_size - overlap
    return [c for c in chunks if c]
```

**Sliding window** chunking:
- `chunk_size=800` characters — each chunk is ~150–200 words (good for embedding models)
- `overlap=100` characters — consecutive chunks share 100 characters

**Why overlap?** Important context often spans a chunk boundary. A sentence might start in chunk 4 and finish in chunk 5. Without overlap, retrieval might miss this sentence (it's in neither chunk completely). With overlap, both chunks contain it partially — so a query about that sentence will match at least one chunk.

```
Document: "...ABCDE...FGHIJ...KLMNO..."
                           ↑800 chars
Chunk 1: "...ABCDE...FGHIJ..."
Chunk 2 starts at: 800 - 100 = 700
Chunk 2: "...GHIJ...KLMNO..."
                    ← 100 chars overlap
```

Default: `chunk_size=800, chunk_overlap=100`. Configurable per-request in `RAGIngestRequest`.

---

## Concept 5: Lazy-Loading the Embedding Model

```python
_EMBEDDING_MODEL_NAME = "BAAI/bge-small-en-v1.5"
_model = None  # module-level None

def _get_embedding_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(_EMBEDDING_MODEL_NAME)
    return _model
```

**Why lazy?** Loading `SentenceTransformer` downloads ~90MB of model weights (on first run) and loads them into memory. Doing this at application startup would:
1. Slow down startup significantly
2. Waste RAM if the RAG endpoints are never called

Lazy loading means the model is only loaded on the **first** call to `/rag/ingest` or `/rag/retrieve`. Subsequent calls reuse `_model` (it's cached in the module-level global).

`global _model` — inside a function, `_model = ...` would create a local variable. `global _model` tells Python we're modifying the module-level `_model`.

`from sentence_transformers import SentenceTransformer` inside the function — deferred import. The `sentence_transformers` library is not imported at module load time, only when first needed.

---

## Concept 6: Embedding with Normalisation

```python
def _embed(texts: List[str]) -> List[List[float]]:
    model = _get_embedding_model()
    embeddings = model.encode(texts, normalize_embeddings=True)
    return embeddings.tolist()
```

`model.encode(texts)` — takes a list of strings, returns a 2D NumPy array of shape `(len(texts), 384)`.

`normalize_embeddings=True` — L2-normalises each embedding vector to unit length (magnitude = 1). This is critical for cosine similarity:

```
cosine_similarity(A, B) = dot(A, B) / (|A| × |B|)
```

If both vectors are unit-length (|A| = |B| = 1), cosine similarity = dot product. This means you can use pgvector's inner product (`<#>`) or just rely on the cosine operator (`<=>`) — both are equivalent for normalised vectors.

**Why does normalisation matter?** Without normalisation, a longer document's chunks might have larger magnitude vectors just because they contain more content, not because they're more relevant. Normalisation ensures magnitude doesn't affect similarity — only direction (meaning) does.

---

## Concept 7: Retrieval via Cosine Distance SQL

```python
distance_expr = f"{embedding_col} <=> CAST(:embedding AS vector({EMBEDDING_DIM}))"

sql = f"""
    SELECT source, chunk_index, content,
           1 - ({distance_expr}) AS similarity
    FROM document_chunks
    {"WHERE source = :source_filter" if data.source_filter else ""}
    ORDER BY {distance_expr}
    LIMIT :top_k
"""
```

`<=>` is pgvector's cosine distance operator. Cosine distance = 1 - cosine similarity. So:
- **Distance = 0**: vectors are identical (same direction) → perfect match
- **Distance = 1**: vectors are perpendicular → unrelated
- **Distance = 2**: vectors point in opposite directions (rare for text)

`1 - ({distance_expr})` converts distance back to similarity (1 = perfect, 0 = unrelated). The response returns `similarity` (not distance) because it's more intuitive.

`ORDER BY {distance_expr}` — sorts from most similar (lowest distance) to least similar. `LIMIT :top_k` returns only the top matches.

`CAST(:embedding AS vector({EMBEDDING_DIM}))` — the query embedding is passed as a Python list string (e.g., `"[0.12, -0.34, ...]"`). PostgreSQL needs to know its type — the `CAST` tells it this is a `vector(384)`.

### Optional source filter

```python
{"WHERE source = :source_filter" if data.source_filter else ""}
```

Python f-string with conditional — if `source_filter` is provided, adds a `WHERE` clause to restrict retrieval to chunks from a specific document. Without it, retrieval searches across all ingested documents.

---

## Re-ingestion: Delete then Insert

```python
# Delete existing chunks for this source to allow re-ingestion
await db.execute(
    text("DELETE FROM document_chunks WHERE source = :source"),
    {"source": data.source},
)
```

Before inserting new chunks, existing chunks from the same source are deleted. This handles the case where a document is re-ingested after being updated — you want the new chunks, not a mix of old and new.

The delete is a raw SQL call (`text(...)`) rather than ORM because bulk deletes via ORM require fetching objects first then deleting them (inefficient). Raw SQL `DELETE WHERE source = ?` is a single round-trip.

---

## End-to-end: POST /rag/ingest

```
POST /rag/ingest
Body: {
  "source": "sebi_circular_2024",
  "content": "The Securities and Exchange Board of India hereby...[5000 chars]...",
  "chunk_size": 800,
  "chunk_overlap": 100
}
         │
         ▼
ingest_document(db, data)
         │
         ├── _chunk_text("The Securities...", 800, 100)
         │       → chunks = ["The Securities...800chars...", "...700chars overlap..."]
         │       → 7 chunks for 5000-char document
         │
         ├── _embed(chunks)
         │       → loads BAAI/bge-small-en-v1.5 (first call)
         │       → model.encode(7 strings, normalize=True)
         │       → 7 × 384 float vectors
         │
         ├── DELETE FROM document_chunks WHERE source = "sebi_circular_2024"
         │
         ├── db.add(DocumentChunk(source, chunk_index=0, content=chunks[0], embedding=embeddings[0]))
         │   db.add(DocumentChunk(source, chunk_index=1, ...))
         │   ... 7 total
         │
         ├── await db.commit()
         │
         ▼
{"source": "sebi_circular_2024", "chunks_stored": 7, "message": "Ingested 7 chunks..."}
```

```
POST /rag/retrieve
Body: {"query": "What is the SIP limit?", "top_k": 3}
         │
         ▼
retrieve_chunks(db, data)
         │
         ├── _embed(["What is the SIP limit?"])
         │       → [0.12, -0.34, 0.78, ...] (384 floats)
         │
         ├── SQL:
         │   SELECT source, chunk_index, content,
         │          1 - (embedding <=> CAST('[0.12,-0.34,...]' AS vector(384))) AS similarity
         │   FROM document_chunks
         │   ORDER BY embedding <=> CAST(...)
         │   LIMIT 3
         │
         ├── rows = 3 most similar chunks
         │
         ▼
{
  "query": "What is the SIP limit?",
  "results": [
    {"source": "sebi_circular_2024", "chunk_index": 3, "content": "...SIP rules...", "similarity": 0.87},
    {"source": "amfi_guidelines", "chunk_index": 1, "content": "...monthly limit...", "similarity": 0.79},
    {"source": "sebi_circular_2024", "chunk_index": 4, "content": "...investment cap...", "similarity": 0.74}
  ]
}
```
