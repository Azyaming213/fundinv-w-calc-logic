from sqlalchemy import Column, Date, Integer, Numeric, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from database import Base


class PortfolioHolding(Base):
    __tablename__ = "portfolio_holdings"
    __table_args__ = (
        UniqueConstraint("investor_id", "fund_id", "snapshot_date", name="uq_portfolio_holdings_investor_fund_date"),
        {"schema": "fundinv"},
    )

    id = Column(Integer, primary_key=True, index=True)
    investor_id = Column(Integer, ForeignKey("fundinv.investors.id"), nullable=False, index=True)
    fund_id = Column(Integer, ForeignKey("fundinv.funds.id"), nullable=True, index=True)
    holding_date = Column(DateTime(timezone=True), nullable=False, index=True)
    snapshot_date = Column(Date, nullable=True, index=True)
    account_value = Column(Numeric(precision=18, scale=4), nullable=False)
    shareholding_pct = Column(Numeric(precision=12, scale=8), nullable=False)
    daily_pnl = Column(Numeric(precision=18, scale=4), default=0)
    fund_nav = Column(Numeric(precision=18, scale=4), nullable=True)
    units = Column(Numeric(precision=28, scale=10), nullable=True)
    nav_per_unit = Column(Numeric(precision=18, scale=8), nullable=True)
    opening_value = Column(Numeric(precision=18, scale=4), nullable=True)
    opening_shareholding_pct = Column(Numeric(precision=12, scale=8), nullable=True)
    closing_value_before_flows = Column(Numeric(precision=18, scale=4), nullable=True)
    net_flow = Column(Numeric(precision=18, scale=4), nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    investor = relationship("Investor")
    fund = relationship("Fund")
