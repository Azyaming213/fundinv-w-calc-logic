from typing import Optional
from datetime import datetime, timezone
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from database import get_db
from models import AuthSession, User
from models.role_claim import RoleClaim
from services.auth_service import decode_access_token
from config import settings


security = HTTPBearer(auto_error=False)


def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    token = credentials.credentials if credentials else request.cookies.get(settings.AUTH_COOKIE_NAME)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_uuid = payload.get("sub")
    token_id = payload.get("jti")
    if not user_uuid or not token_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )
    session = db.query(AuthSession).filter(
        AuthSession.token_id == token_id,
        AuthSession.revoked.is_(False),
        AuthSession.expires_at > datetime.now(timezone.utc),
    ).first()
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session is invalid, expired, or revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter(User.user_id == user_uuid, User.id == session.user_id).first()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive",
        )

    return user


def require_role(allowed_roles: list[str]):
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role.name not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required role: {allowed_roles}",
            )
        return current_user

    return role_checker


def require_claim(claim_key: str):
    """Dependency that checks the current user's role_claims in DB for a specific claim.

    Usage:
        @router.get("/endpoint")
        def handler(current_user: User = Depends(require_claim("funds:create"))):
            ...
    """

    def claim_checker(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        has = (
            db.query(RoleClaim)
            .filter(
                RoleClaim.role_id == current_user.role_id,
                RoleClaim.claim_key == claim_key,
            )
            .first()
        )
        if not has:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required claim: {claim_key}",
            )
        return current_user

    return claim_checker


def require_any_claim(claim_keys: list[str]):
    """Dependency that checks for any of the given claims."""

    def claim_checker(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        count = (
            db.query(RoleClaim)
            .filter(
                RoleClaim.role_id == current_user.role_id,
                RoleClaim.claim_key.in_(claim_keys),
            )
            .count()
        )
        if count == 0:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required one of: {claim_keys}",
            )
        return current_user

    return claim_checker


def get_client_info(request: Request) -> dict:
    return {
        "ip_address": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent"),
    }
