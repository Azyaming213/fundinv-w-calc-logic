from sqlalchemy import Column, Integer, String, Numeric, Boolean, DateTime, Date, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database import Base


class InvestmentAccount(Base):
    __tablename__ = "investment_accounts"
    __table_args__ = {"schema": "fundinv"}

    id = Column(Integer, primary_key=True, index=True)
    investor_id = Column(Integer, ForeignKey("fundinv.investors.id"), nullable=False, index=True)
    fund_id = Column(Integer, ForeignKey("fundinv.funds.id"), nullable=True)

    account_name = Column(String(255), nullable=False)
    account_number = Column(String(50), nullable=True)
    currency = Column(String(3), nullable=False, default="USD")
    status = Column(String(20), nullable=False, default="active")

    total_invested = Column(Numeric(precision=18, scale=4), nullable=False, default=0)
    current_value = Column(Numeric(precision=18, scale=4), nullable=False, default=0)
    manager_fund_balance = Column(JSONB, nullable=False, default={})

    fund_allocations = Column(JSONB, nullable=False, default={})

    investment_strategy = Column(String(30), nullable=False, default="balanced")

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    fund = relationship("Fund")
