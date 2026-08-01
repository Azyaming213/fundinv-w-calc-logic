from pydantic import BaseModel, Field
from typing import Optional, List


class FundResponse(BaseModel):
    id: int
    name: str
    ticker: Optional[str] = None
    description: Optional[str] = None
    fund_type: str
    strategy: Optional[str] = None
    asset_class: Optional[str] = None
    risk_level: Optional[str] = None
    current_price: Optional[float] = None
    change_pct: Optional[float] = None
    ytd_return: Optional[float] = None
    expense_ratio: Optional[float] = None
    aum: Optional[float] = None
    is_featured: bool = False
    manager_name: Optional[str] = None
    review_status: str = "approved"

    class Config:
        from_attributes = True


class FundListResponse(BaseModel):
    success: bool
    data: Optional[dict] = None
    error: Optional[dict] = None


class InvestRequest(BaseModel):
    fund_id: int
    amount: float = Field(..., gt=0)
    investment_account_id: int


class InvestResponse(BaseModel):
    success: bool
    data: Optional[dict] = None
    error: Optional[dict] = None
