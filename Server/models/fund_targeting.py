from sqlalchemy import Column, Integer, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func

from database import Base


class FundTargeting(Base):
    __tablename__ = "fund_targeting"
    __table_args__ = (
        UniqueConstraint("investor_id", "fund_id", name="uq_fund_targeting_investor_fund"),
        {"schema": "fundinv"},
    )

    id = Column(Integer, primary_key=True, index=True)
    investor_id = Column(Integer, ForeignKey("fundinv.investors.id", ondelete="CASCADE"), nullable=False)
    fund_id = Column(Integer, ForeignKey("fundinv.funds.id", ondelete="CASCADE"), nullable=False)
    is_visible = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
