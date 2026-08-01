from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database import Base


class FundValuation(Base):
    """One auditable accounting record per fund and valuation date."""

    __tablename__ = "fund_valuations"
    __table_args__ = (
        UniqueConstraint("fund_id", "valuation_date", name="uq_fund_valuations_fund_date"),
        {"schema": "fundinv"},
    )

    id = Column(Integer, primary_key=True)
    fund_id = Column(Integer, ForeignKey("fundinv.funds.id", ondelete="CASCADE"), nullable=False, index=True)
    valuation_date = Column(Date, nullable=False, index=True)
    opening_assets = Column(Numeric(precision=18, scale=4), nullable=False)
    daily_pnl = Column(Numeric(precision=18, scale=4), nullable=False, default=0)
    closing_assets_before_flows = Column(Numeric(precision=18, scale=4), nullable=False)
    net_flow = Column(Numeric(precision=18, scale=4), nullable=False, default=0)
    closing_assets = Column(Numeric(precision=18, scale=4), nullable=False)
    units_outstanding = Column(Numeric(precision=28, scale=10), nullable=False)
    nav_per_unit = Column(Numeric(precision=18, scale=8), nullable=False)
    status = Column(String(20), nullable=False, default="finalized")
    source = Column(String(30), nullable=False, default="scheduled_snapshot")
    finalized_by_user_id = Column(Integer, ForeignKey("fundinv_auth.users.id"), nullable=True)
    finalized_at = Column(DateTime(timezone=True), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    fund = relationship("Fund")
    finalized_by = relationship("User")
