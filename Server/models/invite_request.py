from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database import Base


class InviteRequest(Base):
    __tablename__ = "invite_requests"
    __table_args__ = {"schema": "fundinv"}

    id = Column(Integer, primary_key=True, index=True)
    requested_by_user_id = Column(Integer, ForeignKey("fundinv_auth.users.id"), nullable=False)
    email = Column(String(255), nullable=False, index=True)
    full_name = Column(String(255), nullable=False)
    role_id = Column(Integer, ForeignKey("fundinv_auth.roles.id"), nullable=False)
    status = Column(String(30), nullable=False, default="pending_admin_review", index=True)
    reviewed_by_user_id = Column(Integer, ForeignKey("fundinv_auth.users.id"), nullable=True)
    review_notes = Column(String(1000), nullable=True)
    invite_id = Column(Integer, ForeignKey("fundinv.invites.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    reviewed_at = Column(DateTime(timezone=True), nullable=True)

    requested_by = relationship("User", foreign_keys=[requested_by_user_id])
    reviewed_by = relationship("User", foreign_keys=[reviewed_by_user_id])
    role = relationship("Role")
    invite = relationship("Invite")
