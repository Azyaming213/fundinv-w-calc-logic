from sqlalchemy import Column, Integer, String, Numeric, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database import Base


class Investor(Base):
    __tablename__ = "investors"
    __table_args__ = {"schema": "fundinv"}

    id = Column(Integer, primary_key=True, index=True)
    manager_id = Column(Integer, ForeignKey("fundinv.managers.id"), nullable=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    full_name = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=False)
    initial_capital = Column(Numeric(precision=18, scale=4), default=0)
    onboarded_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    stripe_connect_account_id = Column(String(255), nullable=True, unique=True)

    manager = relationship("Manager")
