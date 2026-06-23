from fastapi import FastAPI
from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.orm import Session
from backend.app.db.database import engine, get_db
from backend.app.services.user_service import create_user, get_users, get_user_by_id
from backend.app.schemas.user import UserCreate, UserResponse

app = FastAPI()

@app.get("/")
def root():
    return {"message": "running"}

@app.get("/hello/{name}")
def hello(name:str):
    return {"message": f"Hello {name}"}

@app.get("/health")
def health_check():

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return {
            "api": "healthy",
            "database": "healthy"
        }
    except Exception as e:
        return {
            "api": "healthy",
            "database": "unhealthy",
            "error": str(e)
        }


@app.get("/db-test")
def db_test(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"message": "database session working"}

@app.post("/users", response_model=UserResponse)
def create_user_endpoint(user: UserCreate, db: Session = Depends(get_db)):
    return create_user(db, user)

@app.get("/user")
def get_all_users(db:Session = Depends(get_db)):
    return get_users(db)

@app.get("/users/{user_id}")
def get_user_by_id_endpoint(user_id: int, db: Session = Depends(get_db)):
    return get_user_by_id(db, user_id)