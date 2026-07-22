from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database import Base


class FundComponent(Base):
    __tablename__ = "fund_components"
    __table_args__ = {"schema": "fundinv"}

    id = Column(Integer, primary_key=True, index=True)
    fund_id = Column(Integer, ForeignKey("fundinv.funds.id", ondelete="CASCADE"), nullable=False, index=True)
    component_fund_id = Column(Integer, ForeignKey("fundinv.funds.id"), nullable=True, index=True)
    symbol = Column(String(20), nullable=True)
    component_name = Column(String(255), nullable=False)
    asset_type = Column(String(30), nullable=False)
    target_pct = Column(Numeric(7, 4), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    fund = relationship("Fund", foreign_keys=[fund_id])
    component_fund = relationship("Fund", foreign_keys=[component_fund_id])
