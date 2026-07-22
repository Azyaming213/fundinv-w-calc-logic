from typing import Optional
from sqlalchemy.orm import Session

from models import AuditLog, User

AUDIT_ACTIONS = {
    "AUTH_LOGIN_SUCCESS": "auth.login.success",
    "AUTH_LOGIN_FAILED": "auth.login.failed",
    "AUTH_LOGOUT": "auth.logout",
    "AUTH_MFA_ENABLED": "auth.mfa.enabled",
    "AUTH_MFA_DISABLED": "auth.mfa.disabled",
    "AUTH_PASSWORD_RESET": "auth.password.reset",
    "FUND_FLOW_DEPOSIT_REQUESTED": "fund_flow.deposit.requested",
    "FUND_FLOW_DEPOSIT_APPROVED": "fund_flow.deposit.approved",
    "FUND_FLOW_DEPOSIT_COMPLETED": "fund_flow.deposit.completed",
    "FUND_FLOW_DEPOSIT_REJECTED": "fund_flow.deposit.rejected",
    "FUND_FLOW_WITHDRAWAL_REQUESTED": "fund_flow.withdrawal.requested",
    "FUND_FLOW_WITHDRAWAL_APPROVED": "fund_flow.withdrawal.approved",
    "FUND_FLOW_WITHDRAWAL_COMPLETED": "fund_flow.withdrawal.completed",
    "FUND_FLOW_WITHDRAWAL_REJECTED": "fund_flow.withdrawal.rejected",
    "FUND_INVESTED": "fund.invested",
    "TRADE_EXECUTED": "trade.executed",
    "FUND_CREATED": "fund.created",
    "FUND_UPDATED": "fund.updated",
    "FUND_TARGETING_UPDATED": "fund_targeting.updated",
    "USER_CREATED": "user.created",
    "USER_UPDATED": "user.updated",
    "USER_DEACTIVATED": "user.deactivated",
    "INVITE_SENT": "invite.sent",
    "INVITE_REVOKED": "invite.revoked",
}


def get_system_user(db: Session) -> Optional[User]:
    """Return the seeded system user for audit attribution, creating if missing."""
    user = db.query(User).filter(User.email == "system@fundinv.com").first()
    if not user:
        from models import Role
        role = db.query(Role).filter(Role.name == "admin").first()
        if role:
            user = User(
                email="system@fundinv.com",
                full_name="System Actor",
                hashed_password="$2b$12$SYSTEM_NO_LOGIN_SYSUSER",
                role_id=role.id,
                is_active=False,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
    return user


def log_event(
    db: Session,
    action: str,
    user_id: Optional[int] = None,
    details: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    changes: Optional[dict] = None,
    status: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> AuditLog:
    audit = AuditLog(
        user_id=user_id,
        action=action,
        details=details,
        entity_type=entity_type,
        entity_id=entity_id,
        changes=changes,
        status=status,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(audit)
    db.commit()
    db.refresh(audit)
    return audit
