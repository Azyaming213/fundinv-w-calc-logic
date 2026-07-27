from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from database import Base


class FundFlow(Base):
    __tablename__ = "fund_flows"
    __table_args__ = {"schema": "fundinv"}

    id = Column(Integer, primary_key=True, index=True)
    investor_id = Column(Integer, ForeignKey("fundinv.investors.id"), nullable=False, index=True)
    investment_account_id = Column(Integer, ForeignKey("fundinv.investment_accounts.id"), nullable=True, index=True)
    fund_id = Column(Integer, ForeignKey("fundinv.funds.id"), nullable=True, index=True)
    flow_type = Column(String(20), nullable=False)
    amount = Column(Numeric(precision=18, scale=4), nullable=False)
    currency = Column(String(3), nullable=False, default="USD")
    status = Column(String(30), nullable=False, default="pending")
    request_id = Column(String(100), unique=True, nullable=False)
    requested_at = Column(DateTime(timezone=True), server_default=func.now())
    processed_at = Column(DateTime(timezone=True), nullable=True)
    processed_by_user_id = Column(Integer, ForeignKey("fundinv_auth.users.id"), nullable=True)
    notes = Column(String(500), nullable=True)
    provider = Column(String(30), nullable=True)
    provider_reference = Column(String(255), nullable=True, unique=True)
    payment_url = Column(String(2000), nullable=True)
    failure_reason = Column(String(1000), nullable=True)

    investor = relationship("Investor")
    investment_account = relationship("InvestmentAccount")
    fund = relationship("Fund")
    processed_by = relationship("User")
