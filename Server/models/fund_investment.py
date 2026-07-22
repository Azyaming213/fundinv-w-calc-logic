import enum
from sqlalchemy import Column, Integer, Numeric, DateTime, ForeignKey, String
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from database import Base

class InvestmentStatus(str, enum.Enum):
    pending = "pending"
    completed = "completed"
    failed = "failed"

class FundInvestment(Base):
    __tablename__ = "fund_investments"
    __table_args__ = {"schema": "fundinv"}

    id = Column(Integer, primary_key=True, index=True)
    investor_id = Column(Integer, ForeignKey("fundinv.investors.id"), nullable=False, index=True)
    fund_id = Column(Integer, ForeignKey("fundinv.funds.id"), nullable=False)
    amount = Column(Numeric(precision=18, scale=4), nullable=False)
    status = Column(String(20), nullable=False, default=InvestmentStatus.pending.value)
    invested_at = Column(DateTime(timezone=True), server_default=func.now())

    investor = relationship("Investor")
    fund = relationship("Fund")
