FROM python:3.11-slim-bullseye

WORKDIR /workspace

# Install system dependencies (lighter)
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy and install requirements in layers
COPY requirements.txt .

# Install in stages to avoid timeouts
RUN pip install --no-cache-dir --timeout=1000 \
    fastapi uvicorn psycopg2-binary sqlalchemy asyncpg \
    python-dotenv alembic pgvector pydantic pydantic-settings \
    redis celery python-jose[cryptography] passlib[bcrypt]

# Install ML packages separately (they're huge)
RUN pip install --no-cache-dir --timeout=1000 \
    numpy scipy pandas openpyxl pyyaml httpx requests

# Install langchain and ML dependencies
RUN pip install --no-cache-dir --timeout=1000 \
    langchain langgraph langfuse

# Optional: Install torch separately (it's huge)
RUN pip install --no-cache-dir --timeout=1000 \
    torch --index-url https://download.pytorch.org/whl/cpu

# Install remaining packages
RUN pip install --no-cache-dir --timeout=1000 \
    sentence-transformers ragas deepeval ollama

RUN pip install --no-cache-dir --timeout=1000 \
    fastapi uvicorn psycopg2-binary sqlalchemy asyncpg \
    python-dotenv alembic pgvector pydantic pydantic-settings \
    email-validator \
    redis celery python-jose[cryptography] passlib[bcrypt]

COPY . .

EXPOSE 8000

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]