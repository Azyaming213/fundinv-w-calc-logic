from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func

from database import Base


class RoleClaim(Base):
    __tablename__ = "role_claims"
    __table_args__ = (
        UniqueConstraint("role_id", "claim_key", name="uq_role_claims_role_claim"),
        {"schema": "fundinv_auth"},
    )

    id = Column(Integer, primary_key=True, index=True)
    role_id = Column(Integer, ForeignKey("fundinv_auth.roles.id"), nullable=False, index=True)
    claim_key = Column(String(100), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
