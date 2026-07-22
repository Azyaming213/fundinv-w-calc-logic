from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey

from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database import Base



class Invite(Base):
    __tablename__ = "invites"
    __table_args__ = {"schema": "fundinv"}

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), nullable=False, index=True)
    full_name = Column(String(255), nullable=False)
    role_id = Column(Integer, ForeignKey("fundinv_auth.roles.id"), nullable=False)
    token = Column(String(255), unique=True, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used = Column(Boolean, default=False)
    created_by_id = Column(Integer, ForeignKey("fundinv_auth.users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    used_at = Column(DateTime(timezone=True))

    role = relationship("Role")
    created_by = relationship("User", foreign_keys=[created_by_id])
