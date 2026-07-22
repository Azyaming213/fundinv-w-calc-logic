from sqlalchemy import Column, Integer, Numeric, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from database import Base


class PortfolioHolding(Base):
    __tablename__ = "portfolio_holdings"
    __table_args__ = {"schema": "fundinv"}

    id = Column(Integer, primary_key=True, index=True)
    investor_id = Column(Integer, ForeignKey("fundinv.investors.id"), nullable=False, index=True)
    fund_id = Column(Integer, ForeignKey("fundinv.funds.id"), nullable=True, index=True)
    holding_date = Column(DateTime(timezone=True), nullable=False, index=True)
    account_value = Column(Numeric(precision=18, scale=4), nullable=False)
    shareholding_pct = Column(Numeric(precision=10, scale=8), nullable=False)
    daily_pnl = Column(Numeric(precision=18, scale=4), default=0)
    fund_nav = Column(Numeric(precision=18, scale=4), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    investor = relationship("Investor")
    fund = relationship("Fund")
