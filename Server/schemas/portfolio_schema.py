from pydantic import BaseModel, Field
from typing import Optional


class CreateAccountRequest(BaseModel):
    account_name: str = Field(..., min_length=1, max_length=255)
    currency: str = Field(default="USD", max_length=3)
    investment_strategy: str = Field(default="balanced")


class UpdateAccountRequest(BaseModel):
    account_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    investment_strategy: Optional[str] = None


class FundFlowRequest(BaseModel):
    amount: float = Field(..., gt=0)
    investment_account_id: int
    notes: Optional[str] = Field(default=None, max_length=500)


class FundFlowActionRequest(BaseModel):
    notes: Optional[str] = Field(default=None, max_length=500)
