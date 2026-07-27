from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from database import SessionLocal
from models import AuthSession, Invite, LoginAttempt


def expire_unused_invites():
    db: Session = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        expired = (
            db.query(Invite)
            .filter(Invite.used == False, Invite.expires_at < now)
            .count()
        )
        if expired > 0:
            print(f"[CLEANUP] Found {expired} expired, unused invites")
    finally:
        db.close()


def cleanup_security_state():
    """Remove expired sessions and stale throttle rows without touching active sessions."""
    db: Session = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        session_cutoff = now - timedelta(days=7)
        throttle_cutoff = now - timedelta(days=1)
        db.query(AuthSession).filter(
            (AuthSession.expires_at < session_cutoff)
            | ((AuthSession.revoked.is_(True)) & (AuthSession.revoked_at < session_cutoff))
        ).delete(synchronize_session=False)
        db.query(LoginAttempt).filter(
            LoginAttempt.updated_at < throttle_cutoff,
            (LoginAttempt.blocked_until.is_(None)) | (LoginAttempt.blocked_until < now),
        ).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()
