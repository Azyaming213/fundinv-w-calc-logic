from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database import Base


class FundPosition(Base):
    """Authoritative unit holding for one investment account and fund."""

    __tablename__ = "fund_positions"
    __table_args__ = (
        UniqueConstraint("investment_account_id", "fund_id", name="uq_fund_positions_account_fund"),
        {"schema": "fundinv"},
    )

    id = Column(Integer, primary_key=True)
    investment_account_id = Column(
        Integer,
        ForeignKey("fundinv.investment_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    investor_id = Column(
        Integer,
        ForeignKey("fundinv.investors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    fund_id = Column(
        Integer,
        ForeignKey("fundinv.funds.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    units = Column(Numeric(precision=28, scale=10), nullable=False, default=0)
    cost_basis = Column(Numeric(precision=18, scale=4), nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    investment_account = relationship("InvestmentAccount")
    investor = relationship("Investor")
    fund = relationship("Fund")
