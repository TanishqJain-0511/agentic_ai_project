from sqlalchemy.orm import Session
from backend.app.models.user import User
from backend.app.schemas.user import UserCreate

def create_user(db:Session, user:UserCreate):

    new_user = User(
        name=user.name,
        email=user.email
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user

def get_users(db:Session):
    users = db.query(User).all()
    return users

def get_user_by_id(db:Session, user_id: int):
    return (
        db.query(User)
        .filter(User.id==user_id)
        .first()
    )