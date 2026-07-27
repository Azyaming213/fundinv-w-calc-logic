from sqlalchemy import Column, Integer, Numeric, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from database import Base


class FundBalanceEntry(Base):
    __tablename__ = "fund_balance_entries"
    __table_args__ = (
        UniqueConstraint("fund_flow_id", name="uq_fund_balance_entries_flow_id"),
        {"schema": "fundinv"},
    )

    id = Column(Integer, primary_key=True, index=True)
    investment_account_id = Column(Integer, ForeignKey("fundinv.investment_accounts.id"), nullable=False, index=True)
    fund_id = Column(Integer, ForeignKey("fundinv.funds.id"), nullable=False, index=True)
    fund_flow_id = Column(Integer, ForeignKey("fundinv.fund_flows.id"), nullable=True, index=True)
    entry_type = Column(String(30), nullable=False)
    amount = Column(Numeric(18, 4), nullable=False)
    units = Column(Numeric(28, 10), nullable=True)
    nav_per_unit = Column(Numeric(18, 8), nullable=True)
    provider_reference = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    investment_account = relationship("InvestmentAccount")
    fund = relationship("Fund")
    fund_flow = relationship("FundFlow")
