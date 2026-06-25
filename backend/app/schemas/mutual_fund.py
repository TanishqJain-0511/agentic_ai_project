from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class MutualFundResponse(BaseModel):
    id: int
    scheme_code: str
    scheme_name: str
    net_asset_value: Optional[float] = None
    nav_date: Optional[str] = None
    category: Optional[str] = None
    risk_grade: Optional[str] = None
    expense_ratio: Optional[float] = None
    aum_in_crores: Optional[float] = None
    last_updated: Optional[datetime] = None

    class Config:
        from_attributes = True



class MutualFundSyncResponse(BaseModel):
    synced: int
    failed: int
    message: str
