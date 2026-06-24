from sqlalchemy import Column, Integer, String
from backend.app.db.database import Base
from sqlalchemy.orm import relationship

class User(Base):

    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    field_description = Column(String, nullable=False)

    financial_profiles = relationship(
        "FinancialProfile",
        back_populates="user",
    )