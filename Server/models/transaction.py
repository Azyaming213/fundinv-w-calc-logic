from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey, BigInteger, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from database import Base


class InvestmentTransaction(Base):
    __tablename__ = "investment_transactions"
    __table_args__ = {"schema": "fundinv"}

    id = Column(Integer, primary_key=True, index=True)
    ticket = Column(String(50), unique=True, nullable=False, index=True)
    order_ticket = Column(String(50), nullable=True, index=True)
    investor_id = Column(Integer, ForeignKey("fundinv.investors.id"), nullable=True, index=True)
    fund_id = Column(Integer, ForeignKey("fundinv.funds.id"), nullable=True, index=True)
    investment_account_id = Column(Integer, ForeignKey("fundinv.investment_accounts.id"), nullable=True, index=True)
    position_id = Column(String(64), nullable=True, index=True)
    trade_time = Column(DateTime(timezone=True), nullable=False, index=True)
    time_msc = Column(BigInteger, nullable=True)
    trade_type = Column(String(20), nullable=False)
    entry = Column(String(4), nullable=True)
    symbol = Column(String(20), nullable=False, index=True)
    volume = Column(Numeric(precision=18, scale=4), nullable=False)
    price = Column(Numeric(precision=18, scale=8), nullable=False)
    profit = Column(Numeric(precision=18, scale=4), default=0)
    commission = Column(Numeric(precision=18, scale=4), default=0)
    swap = Column(Numeric(precision=18, scale=4), default=0)
    fee = Column(Numeric(precision=18, scale=4), default=0)
    net_pnl = Column(Numeric(precision=18, scale=4), default=0)
    sl = Column(Numeric(precision=18, scale=8), nullable=True)
    tp = Column(Numeric(precision=18, scale=8), nullable=True)
    magic = Column(String(64), nullable=True)
    reason = Column(String(255), nullable=True)
    comment = Column(Text, nullable=True)
    external_id = Column(String(100), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    investor = relationship("Investor")
    fund = relationship("Fund")
    investment_account = relationship("InvestmentAccount")
