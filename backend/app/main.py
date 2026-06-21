from fastapi import FastAPI

app = FastAPI(
    title="Agentic Wealth Management Copilot API",
    description="API for financial profile management, recommendations, and agentic workflows.",
    version="0.1.0",
)

@app.get("/")
async def read_root():
    return {"message": "Welcome to the Agentic Wealth Management Copilot API!"}

@app.get("/health")
async def health_check():
    return {"status": "ok"}
