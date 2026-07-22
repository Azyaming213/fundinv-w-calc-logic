from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from database import Base


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = {"schema": "fundinv"}

    id = Column(Integer, primary_key=True, index=True)
    investor_id = Column(Integer, ForeignKey("fundinv.investors.id"), nullable=False, index=True)
    investment_account_id = Column(Integer, ForeignKey("fundinv.investment_accounts.id"), nullable=False, index=True)
    fund_id = Column(Integer, ForeignKey("fundinv.funds.id"), nullable=True, index=True)
    alpaca_order_id = Column(String(100), nullable=True)
    symbol = Column(String(20), nullable=False, index=True)
    side = Column(String(10), nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    filled_qty = Column(Numeric(18, 8), nullable=True)
    filled_price = Column(Numeric(18, 8), nullable=True)
    status = Column(String(20), nullable=False, default="new")
    performed_by_user_id = Column(Integer, ForeignKey("fundinv_auth.users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    investor = relationship("Investor")
    investment_account = relationship("InvestmentAccount")
    fund = relationship("Fund")
