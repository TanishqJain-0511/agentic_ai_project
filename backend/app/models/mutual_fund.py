from sqlalchemy import Column, Integer, String, Float, DateTime, func
from backend.app.db.database import Base


class MutualFund(Base):

    __tablename__ = "mutual_funds"

    id = Column(Integer, primary_key=True, index=True)
    scheme_code = Column(String, unique=True, nullable=False, index=True)
    scheme_name = Column(String, nullable=False)
    net_asset_value = Column(Float, nullable=True)
    nav_date = Column(String, nullable=True)
    category = Column(String, nullable=True)      # Large Cap, Mid Cap, Small Cap, etc.
    risk_grade = Column(String, nullable=True)    # Low | Moderate | High | Very High
    expense_ratio = Column(Float, nullable=True)  # percentage
    aum_in_crores = Column(Float, nullable=True)  # AUM in crores (INR)
    last_updated = Column(DateTime(timezone=True), nullable=True, default=func.now(), onupdate=func.now())
