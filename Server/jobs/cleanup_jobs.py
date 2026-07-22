from datetime import datetime, timezone

from sqlalchemy.orm import Session

from database import SessionLocal
from models import Invite


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
