from sqlalchemy.orm import Session
from backend.app.models.financial_profile import FinancialProfile
from backend.app.schemas.financial_profile import FinancialProfileCreate

def create_financial_profile(db:Session, financial_profile_data:FinancialProfileCreate):

    """
    Creates a new financial profile for a specific user
    :param db:
    :param user:
    :param financial_profile:
    :return:
    """
    new_financial_profile = FinancialProfile(
        **financial_profile_data.model_dump()
    )

    db.add(new_financial_profile)
    db.commit()
    db.refresh(new_financial_profile)

    return new_financial_profile

def get_all_financial_profile(db:Session):
    """
    Retrieves all financial profiles
    :param db:
    :return:
    """
    return db.query(FinancialProfile).all()

def get_financial_profile_by_user_id(db:Session, user_id: int):
    """
    Retrieves a financial profile for a specific user
    :param db:
    :param user_id:
    :return:
    """
    return (
        db.query(FinancialProfile)
        .filter(FinancialProfile.user_id==user_id)
        .first()

    )