from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.sql import func

from database import Base


class LoginAttempt(Base):
    __tablename__ = "login_attempts"
    __table_args__ = {"schema": "fundinv_auth"}

    id = Column(Integer, primary_key=True)
    throttle_key = Column(String(64), unique=True, nullable=False, index=True)
    failure_count = Column(Integer, nullable=False, default=0)
    window_started_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    blocked_until = Column(DateTime(timezone=True), nullable=True, index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
