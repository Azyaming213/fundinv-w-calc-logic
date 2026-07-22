from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database import Base


class FeedbackTicket(Base):
    __tablename__ = "feedback_tickets"
    __table_args__ = {"schema": "fundinv"}

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("fundinv_auth.users.id"), nullable=False, index=True)
    category = Column(String(50), nullable=False, default="general")
    subject = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    status = Column(String(30), nullable=False, default="open", index=True)
    priority = Column(String(20), nullable=False, default="normal")
    assigned_to_user_id = Column(Integer, ForeignKey("fundinv_auth.users.id"), nullable=True)
    response = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", foreign_keys=[user_id])
    assigned_to = relationship("User", foreign_keys=[assigned_to_user_id])
