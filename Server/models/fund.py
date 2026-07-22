import enum

from sqlalchemy import Column, Integer, String, Numeric, DateTime, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database import Base


class FundType(str, enum.Enum):
    etf = "etf"
    mutual_fund = "mutual_fund"
    hedge_fund = "hedge_fund"
    stock = "stock"
    crypto = "crypto"
    bond = "bond"
    managed = "managed"
    other = "other"


class Fund(Base):
    __tablename__ = "funds"
    __table_args__ = {"schema": "fundinv"}

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    ticker = Column(String(20), nullable=True, unique=True, index=True)
    description = Column(String(1000), nullable=True)
    fund_type = Column(String(30), nullable=False, default=FundType.other.value)

    strategy = Column(String(30), nullable=True, index=True)
    asset_class = Column(String(30), nullable=True, index=True)
    risk_level = Column(String(20), nullable=True)

    current_price = Column(Numeric(precision=18, scale=8), nullable=True)
    change_pct = Column(Numeric(precision=10, scale=4), nullable=True)
    ytd_return = Column(Numeric(precision=10, scale=4), nullable=True)
    expense_ratio = Column(Numeric(precision=6, scale=4), nullable=True)
    aum = Column(Numeric(precision=18, scale=2), nullable=True)

    is_featured = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    creator_manager_id = Column(Integer, ForeignKey("fundinv.managers.id"), nullable=True, index=True)
    portfolio_composition = Column(JSONB, nullable=True)
    review_status = Column(String(30), nullable=False, default="approved", index=True)
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    reviewed_by_user_id = Column(Integer, ForeignKey("fundinv_auth.users.id"), nullable=True)
    review_notes = Column(String(1000), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    created_by = relationship("Manager")
    reviewed_by = relationship("User", foreign_keys=[reviewed_by_user_id])
