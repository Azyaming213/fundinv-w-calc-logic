from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database import Base


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    __table_args__ = {"schema": "fundinv_auth"}

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("fundinv_auth.users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_id = Column(String(64), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    revoked = Column(Boolean, nullable=False, default=False, index=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    ip_address = Column(String(64), nullable=True)
    user_agent = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_seen_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User")
