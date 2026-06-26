from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.database import engine, get_db
from backend.app.db.init_db import init_db
from backend.app.services.user_service import create_user, get_users, get_user_by_id
from backend.app.schemas.user import UserCreate, UserResponse
from backend.app.services.financial_profile_service import create_financial_profile, get_all_financial_profile, get_financial_profile_by_user_id
from backend.app.schemas.financial_profile import FinancialProfileCreate, FinancialProfileResponse
from backend.app.services.investment_goal_service import create_investment_goal,get_investment_goals_by_user_id,get_investment_goal_by_id
from backend.app.schemas.investment_goal import InvestmentGoalCreate, InvestmentGoalResponse
from backend.app.services.risk_assessment_service import create_risk_assessment, get_risk_assessment_by_user_id
from backend.app.schemas.risk_assessment import RiskAssessmentCreate,RiskAssessmentResponse,QuestionsResponse,QUESTIONNAIRE_QUESTIONS
from backend.app.services.financial_health_service import compute_financial_health
from backend.app.schemas.financial_health import FinancialHealthResponse
from backend.app.services.risk_scoring_service import compute_risk_score
from backend.app.schemas.risk_score import RiskScoreRequest, RiskScoreResponse
from backend.app.services.allocation_service import compute_allocation
from backend.app.schemas.allocation import AllocationRequest, AllocationResponse
from backend.app.services.mutual_fund_data_service import (
    sync_mutual_funds,
    get_all_mutual_funds,
    get_mutual_fund_by_scheme_code,
)
from backend.app.schemas.mutual_fund import MutualFundResponse, MutualFundSyncResponse

from backend.app.services.mutual_fund_research_service import run_mutual_fund_research
from backend.app.schemas.mutual_fund_research import MutualFundResearchRequest, MutualFundResearchResponse

from backend.app.services.policy_engine import check_policy
from backend.app.schemas.policy import PolicyCheckRequest, PolicyCheckResponse

from backend.app.services.compliance_service import run_compliance_agent
from backend.app.schemas.compliance import ComplianceRequest, ComplianceResponse

from backend.app.services.simulation_service import run_simulation
from backend.app.schemas.simulation import SimulationRequest, SimulationResponse

from backend.app.services.rag_service import ingest_document, retrieve_chunks, generate_rag_answer
from backend.app.schemas.rag import (
    RAGIngestRequest,
    RAGIngestResponse,
    RAGRetrieveRequest,
    RAGRetrieveResponse,
    RAGGenerateRequest,
    RAGGenerateResponse,
)

from backend.app.services.explanation_service import generate_explanation
from backend.app.schemas.explanation import ExplanationRequest, ExplanationResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield
    await engine.dispose()


app = FastAPI(lifespan=lifespan)


@app.get("/")
async def root():
    return {"message": "running"}


@app.get("/hello/{name}")
async def hello(name: str):
    return {"message": f"Hello {name}"}


@app.get("/health")
async def health_check():
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        return {"api": "healthy", "database": "healthy"}
    except Exception as e:
        return {"api": "healthy", "database": "unhealthy", "error": str(e)}


@app.get("/db-test")
async def db_test(db: AsyncSession = Depends(get_db)):
    await db.execute(text("SELECT 1"))
    return {"message": "database session working"}


@app.post("/users", response_model=UserResponse)
async def create_user_endpoint(user: UserCreate, db: AsyncSession = Depends(get_db)):
    return await create_user(db, user)


@app.get("/users")
async def get_all_users(db: AsyncSession = Depends(get_db)):
    return await get_users(db)


@app.get("/users/{user_id}")
async def get_user_by_id_endpoint(user_id: int, db: AsyncSession = Depends(get_db)):
    return await get_user_by_id(db, user_id)


@app.post("/financial-profile", response_model=FinancialProfileResponse)
async def create_financial_profile_endpoint(
    financialProfile: FinancialProfileCreate, db: AsyncSession = Depends(get_db)
):
    return await create_financial_profile(db, financialProfile)


@app.get("/all-financial-profile")
async def get_all_financial_profile_endpoint(db: AsyncSession = Depends(get_db)):
    return await get_all_financial_profile(db)


@app.get("/financial-profile/{user_id}")
async def get_financial_profile_by_user_id_endpoint(
    user_id: int, db: AsyncSession = Depends(get_db)
):
    return await get_financial_profile_by_user_id(db, user_id)


@app.post("/investment-goals", response_model=InvestmentGoalResponse)
async def create_investment_goal_endpoint(
    goal_data: InvestmentGoalCreate, db: AsyncSession = Depends(get_db)
):
    return await create_investment_goal(db, goal_data)


@app.get("/investment-goals/{user_id}")
async def get_investment_goals_by_user_id_endpoint(
    user_id: int, db: AsyncSession = Depends(get_db)
):
    return await get_investment_goals_by_user_id(db, user_id)


@app.get("/investment-goals/goal/{goal_id}")
async def get_goal_by_id_endpoint(goal_id: int, db: AsyncSession = Depends(get_db)):
    return await get_investment_goal_by_id(db, goal_id)


@app.get("/risk-assessment/questions", response_model=QuestionsResponse)
async def get_risk_assessment_questions():
    return {"questions": QUESTIONNAIRE_QUESTIONS}


@app.post("/risk-assessment", response_model=RiskAssessmentResponse)
async def create_risk_assessment_endpoint(
    data: RiskAssessmentCreate, db: AsyncSession = Depends(get_db)
):
    return await create_risk_assessment(db, data)


@app.get("/risk-assessment/{user_id}", response_model=RiskAssessmentResponse)
async def get_risk_assessment_by_user_id_endpoint(
    user_id: int, db: AsyncSession = Depends(get_db)
):
    return await get_risk_assessment_by_user_id(db, user_id)


@app.get("/financial-health/{user_id}", response_model=FinancialHealthResponse)
async def get_financial_health_endpoint(user_id: int, db: AsyncSession = Depends(get_db)):
    return await compute_financial_health(db, user_id)


@app.post("/risk-score", response_model=RiskScoreResponse)
async def compute_risk_score_endpoint(
    data: RiskScoreRequest, db: AsyncSession = Depends(get_db)
):
    return await compute_risk_score(db, data)


@app.post("/allocation", response_model=AllocationResponse)
async def compute_allocation_endpoint(
    data: AllocationRequest, db: AsyncSession = Depends(get_db)
):
    return await compute_allocation(db, data)


@app.post("/mutual-funds/sync", response_model=MutualFundSyncResponse)
async def sync_mutual_funds_endpoint(db: AsyncSession = Depends(get_db)):
    return await sync_mutual_funds(db)


@app.get("/mutual-funds", response_model=List[MutualFundResponse])
async def get_all_mutual_funds_endpoint(category: Optional[str] = None, risk_grade: Optional[str] = None, db: AsyncSession = Depends(get_db), ):
    return await get_all_mutual_funds(db, category=category, risk_grade=risk_grade)


@app.get("/mutual-funds/{scheme_code}", response_model=MutualFundResponse)
async def get_mutual_fund_by_scheme_code_endpoint(scheme_code: str, db: AsyncSession = Depends(get_db)):
    return await get_mutual_fund_by_scheme_code(db, scheme_code)


@app.post("/mutual-fund-research", response_model=MutualFundResearchResponse)
async def mutual_fund_research_endpoint(data: MutualFundResearchRequest, db: AsyncSession = Depends(get_db)):
    return await run_mutual_fund_research(db, data)


@app.post("/policy-check", response_model=PolicyCheckResponse)
async def policy_check_endpoint(data: PolicyCheckRequest):
    return check_policy(data)


@app.post("/compliance-check", response_model=ComplianceResponse)
async def compliance_check_endpoint(data: ComplianceRequest, db: AsyncSession = Depends(get_db)):
    return await run_compliance_agent(db, data)


# ── Phase 10: Monte Carlo Simulation ─────────────────────────────────────────

@app.post("/simulate", response_model=SimulationResponse)
async def simulate_endpoint(data: SimulationRequest):
    return run_simulation(data)


# ── Phase 11: RAG Knowledge Base ──────────────────────────────────────────────

@app.post("/rag/ingest", response_model=RAGIngestResponse)
async def rag_ingest_endpoint(data: RAGIngestRequest, db: AsyncSession = Depends(get_db)):
    return await ingest_document(db, data)


@app.post("/rag/retrieve", response_model=RAGRetrieveResponse)
async def rag_retrieve_endpoint(data: RAGRetrieveRequest, db: AsyncSession = Depends(get_db)):
    return await retrieve_chunks(db, data)


@app.post("/rag/generate", response_model=RAGGenerateResponse)
async def rag_generate_endpoint(data: RAGGenerateRequest, db: AsyncSession = Depends(get_db)):
    return await generate_rag_answer(db, data)


# ── Phase 12: Explanation Generator ──────────────────────────────────────────

@app.post("/explain", response_model=ExplanationResponse)
async def explain_endpoint(data: ExplanationRequest):
    return await generate_explanation(data)
