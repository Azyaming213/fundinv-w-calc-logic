import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from database import get_db
from models import User, Role, Invite, PasswordResetToken, Investor, Manager, InviteRequest
from schemas.auth_schema import (
    LoginRequest,
    RegisterRequest,
    StandardResponse,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    InviteCreateRequest,
    MfaVerifyRequest,
    MfaLoginRequest,
)
from services.auth_service import hash_password, verify_password, create_access_token, create_mfa_token, decode_mfa_token
from services.audit_service import log_event, AUDIT_ACTIONS
from services.email_service import send_invite_email
from services.mfa_service import generate_mfa_secret, generate_otpauth_uri, generate_qr_code_base64, verify_totp
from dependencies import get_current_user, require_claim, require_any_claim, get_client_info
import appconstants as AppConstants


router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post("/register", response_model=StandardResponse)
def register(request: RegisterRequest, req: Request, db: Session = Depends(get_db)):
    invite = db.query(Invite).filter(Invite.token == request.token).first()

    if invite is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid invitation token",
        )

    if invite.used:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invitation already used",
        )

    if invite.expires_at < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invitation has expired",
        )

    existing_user = db.query(User).filter(User.email == invite.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists",
        )

    user = User(
        email=invite.email,
        full_name=invite.full_name,
        hashed_password=hash_password(request.password),
        role_id=invite.role_id,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    if invite.role and invite.role.name == "investor":
        manager_id = None
        if invite.created_by:
            creator_role = invite.created_by.role
            if creator_role and creator_role.name == AppConstants.ROLES["MANAGER"]:
                mgr = db.query(Manager).filter(Manager.email == invite.created_by.email).first()
                if mgr:
                    manager_id = mgr.id

        investor = Investor(
            email=user.email,
            full_name=user.full_name,
            is_active=True,
            manager_id=manager_id,
        )
        db.add(investor)
        db.commit()
    elif invite.role and invite.role.name == "manager":
        manager = Manager(
            email=user.email,
            full_name=user.full_name,
            is_active=True,
        )
        db.add(manager)
        db.commit()

    invite.used = True
    invite.used_at = datetime.now(timezone.utc)

    db.commit()

    client_info = get_client_info(req)
    log_event(
        db=db,
        user_id=user.id,
        action=AUDIT_ACTIONS["USER_CREATED"],
        details=f"User registered via invite {invite.id}",
        entity_type="user",
        entity_id=user.id,
        status="success",
        **client_info,
    )

    return StandardResponse(
        success=True,
        data={"user_id": str(user.user_id), "email": user.email},
        error=None,
    )


@router.post("/login", response_model=StandardResponse)
def login(request: LoginRequest, req: Request, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == request.email).first()
    client_info = get_client_info(req)

    if user is None or not verify_password(request.password, user.hashed_password):
        log_event(
            db=db,
            action=AUDIT_ACTIONS["AUTH_LOGIN_FAILED"],
            details=f"Failed login attempt for {request.email}",
            entity_type="user",
            status="failure",
            **client_info,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user.is_active:
        log_event(
            db=db,
            user_id=user.id,
            action=AUDIT_ACTIONS["AUTH_LOGIN_FAILED"],
            details="Inactive account login attempt",
            entity_type="user",
            entity_id=user.id,
            status="failure",
            **client_info,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive",
        )

    if user.mfa_enabled:
        mfa_token = create_mfa_token(user_id=str(user.user_id), email=user.email)

        log_event(
            db=db,
            user_id=user.id,
            action=AUDIT_ACTIONS["AUTH_LOGIN_SUCCESS"],
            entity_type="user",
            entity_id=user.id,
            changes={"mfa_required": True},
            status="success",
            **client_info,
        )

        return StandardResponse(
            success=True,
            data={
                "mfa_required": True,
                "mfa_token": mfa_token,
                "user_id": str(user.user_id),
            },
            error=None,
        )

    user.last_login_at = datetime.now(timezone.utc)
    db.commit()

    token = create_access_token(
        user_id=str(user.user_id),
        role=user.role.name,
        email=user.email,
        full_name=user.full_name,
        claims=AppConstants.ROLE_CLAIMS.get(user.role.name, []),
    )

    log_event(
        db=db,
        user_id=user.id,
        action=AUDIT_ACTIONS["AUTH_LOGIN_SUCCESS"],
        entity_type="user",
        entity_id=user.id,
        status="success",
        **client_info,
    )

    return StandardResponse(
        success=True,
        data={
            "access_token": token,
            "token_type": "bearer",
            "user": {
                "user_id": str(user.user_id),
                "email": user.email,
                "full_name": user.full_name,
                "role": user.role.name,
                "is_active": user.is_active,
            },
        },
        error=None,
    )


@router.post("/logout", response_model=StandardResponse)
def logout(req: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    client_info = get_client_info(req)
    log_event(
        db=db,
        user_id=current_user.id,
        action=AUDIT_ACTIONS["AUTH_LOGOUT"],
        entity_type="user",
        entity_id=current_user.id,
        status="success",
        **client_info,
    )
    return StandardResponse(success=True, data={"message": "Logged out"}, error=None)


@router.get("/me", response_model=StandardResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return StandardResponse(
        success=True,
        data={
            "user_id": str(current_user.user_id),
            "email": current_user.email,
            "full_name": current_user.full_name,
            "role": current_user.role.name,
            "is_active": current_user.is_active,
            "mfa_enabled": current_user.mfa_enabled,
            "last_login_at": (
                current_user.last_login_at.isoformat()
                if current_user.last_login_at
                else None
            ),
        },
        error=None,
    )


@router.post("/forgot-password", response_model=StandardResponse)
def forgot_password(request: ForgotPasswordRequest, req: Request, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == request.email).first()
    client_info = get_client_info(req)

    if user:
        token = secrets.token_urlsafe(32)
        reset = PasswordResetToken(
            user_id=user.id,
            token=token,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        db.add(reset)
        db.commit()

        log_event(
            db=db,
            user_id=user.id,
            action=AUDIT_ACTIONS["AUTH_PASSWORD_RESET"],
            entity_type="user",
            entity_id=user.id,
            status="success",
            **client_info,
        )

        print(f"\n[DEV] Password reset token for {request.email}: {token}\n")

    return StandardResponse(
        success=True,
        data={"message": "If an account exists with this email, a reset link has been sent"},
        error=None,
    )


@router.post("/reset-password", response_model=StandardResponse)
def reset_password(request: ResetPasswordRequest, req: Request, db: Session = Depends(get_db)):
    reset = (
        db.query(PasswordResetToken)
        .filter(PasswordResetToken.token == request.token)
        .first()
    )

    if reset is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid reset token",
        )

    if reset.used:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reset token already used",
        )

    if reset.expires_at < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reset token has expired",
        )

    user = db.query(User).filter(User.id == reset.user_id).first()
    user.hashed_password = hash_password(request.new_password)
    reset.used = True
    reset.used_at = datetime.now(timezone.utc)
    db.commit()

    client_info = get_client_info(req)
    log_event(
        db=db,
        user_id=user.id,
        action=AUDIT_ACTIONS["AUTH_PASSWORD_RESET"],
        entity_type="user",
        entity_id=user.id,
        status="success",
        **client_info,
    )

    return StandardResponse(
        success=True,
        data={"message": "Password reset successful"},
        error=None,
    )


@router.post("/invites", response_model=StandardResponse)
def create_invite(
    request: InviteCreateRequest,
    req: Request,
    current_user: User = Depends(require_claim(AppConstants.CLAIMS["createInvites"])),
    db: Session = Depends(get_db),
):
    existing_user = db.query(User).filter(User.email == request.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists",
        )

    role = db.query(Role).filter(Role.name == request.role).first()
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role: {request.role}",
        )

    token = secrets.token_urlsafe(32)
    invite = Invite(
        email=request.email,
        full_name=request.full_name,
        role_id=role.id,
        token=token,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        created_by_id=current_user.id,
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)

    client_info = get_client_info(req)
    log_event(
        db=db,
        user_id=current_user.id,
        action=AUDIT_ACTIONS["INVITE_SENT"],
        details=f"Invite created for {request.email} as {request.role}",
        entity_type="invite",
        entity_id=invite.id,
        status="success",
        **client_info,
    )

    email_sent = send_invite_email(
        to_email=invite.email,
        full_name=invite.full_name,
        token=token,
        expires_at=invite.expires_at.isoformat(),
        role=request.role,
    )

    return StandardResponse(
        success=True,
        data={
            "invite_id": invite.id,
            "token": token,
            "email": invite.email,
            "expires_at": invite.expires_at.isoformat(),
            "email_sent": email_sent,
        },
        error=None,
    )


@router.post("/invite-requests", response_model=StandardResponse)
def request_invite(
    request: InviteCreateRequest,
    current_user: User = Depends(require_claim(AppConstants.CLAIMS["requestInvites"])),
    db: Session = Depends(get_db),
):
    if request.role not in (AppConstants.ROLES["INVESTOR"], AppConstants.ROLES["MANAGER"], AppConstants.ROLES["OPERATIONS"]):
        raise HTTPException(status_code=400, detail="Invalid requested role")
    if db.query(User).filter(User.email == request.email).first():
        raise HTTPException(status_code=400, detail="An account with this email already exists")
    role = db.query(Role).filter(Role.name == request.role).first()
    if not role:
        raise HTTPException(status_code=400, detail="Role not found")
    invite_request = InviteRequest(
        requested_by_user_id=current_user.id,
        email=request.email,
        full_name=request.full_name,
        role_id=role.id,
        status="pending_admin_review",
    )
    db.add(invite_request)
    db.commit()
    db.refresh(invite_request)
    log_event(db=db, user_id=current_user.id, action=AUDIT_ACTIONS["INVITE_SENT"],
              details=f"Invite requested for {request.email} as {request.role}", entity_type="invite_request",
              entity_id=invite_request.id, status="pending")
    return StandardResponse(success=True, data={"request_id": invite_request.id, "status": invite_request.status}, error=None)


@router.get("/invites", response_model=StandardResponse)
def list_invites(
    current_user: User = Depends(require_claim(AppConstants.CLAIMS["readInvites"])),
    db: Session = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    invites = db.query(Invite).order_by(Invite.created_at.desc()).all()

    invite_list = []
    for invite in invites:
        invite_list.append({
            "id": invite.id,
            "email": invite.email,
            "full_name": invite.full_name,
            "role": invite.role.name if invite.role else "unknown",
            "token": invite.token,
            "expires_at": invite.expires_at.isoformat(),
            "is_expired": not invite.used and invite.expires_at < now,
            "used": invite.used,
            "used_at": invite.used_at.isoformat() if invite.used_at else None,
            "created_at": invite.created_at.isoformat() if invite.created_at else None,
        })

    return StandardResponse(
        success=True,
        data={"invites": invite_list},
        error=None,
    )


@router.delete("/invites/{invite_id}", response_model=StandardResponse)
def delete_invite(
    invite_id: int,
    current_user: User = Depends(require_claim(AppConstants.CLAIMS["writeInvites"])),
    db: Session = Depends(get_db),
):
    invite = db.query(Invite).filter(Invite.id == invite_id).first()
    if invite is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invite not found",
        )

    db.delete(invite)
    db.commit()

    log_event(
        db=db,
        user_id=current_user.id,
        action=AUDIT_ACTIONS["INVITE_REVOKED"],
        details=f"Invite for {invite.email} deleted",
        entity_type="invite",
        entity_id=invite_id,
        status="success",
    )

    return StandardResponse(
        success=True,
        data={"message": f"Invite for {invite.email} deleted"},
        error=None,
    )


@router.post("/invites/{invite_id}/resend", response_model=StandardResponse)
def resend_invite(
    invite_id: int,
    req: Request,
    current_user: User = Depends(require_claim(AppConstants.CLAIMS["writeInvites"])),
    db: Session = Depends(get_db),
):
    invite = db.query(Invite).filter(Invite.id == invite_id).first()
    if invite is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invite not found",
        )

    if invite.used:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot resend an already used invite",
        )

    new_token = secrets.token_urlsafe(32)
    invite.token = new_token
    invite.expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    db.commit()

    email_sent = send_invite_email(
        to_email=invite.email,
        full_name=invite.full_name,
        token=new_token,
        expires_at=invite.expires_at.isoformat(),
        role=invite.role.name if invite.role else "investor",
    )

    client_info = get_client_info(req)
    log_event(
        db=db,
        user_id=current_user.id,
        action=AUDIT_ACTIONS["INVITE_SENT"],
        details=f"Invite resent for {invite.email}",
        entity_type="invite",
        entity_id=invite.id,
        status="success",
        **client_info,
    )

    return StandardResponse(
        success=True,
        data={
            "invite_id": invite.id,
            "email": invite.email,
            "expires_at": invite.expires_at.isoformat(),
            "email_sent": email_sent,
        },
        error=None,
    )


@router.post("/mfa/setup", response_model=StandardResponse)
def mfa_setup(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.mfa_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA is already enabled",
        )

    secret = generate_mfa_secret()
    otpauth_uri = generate_otpauth_uri(secret, current_user.email)
    qr_base64 = generate_qr_code_base64(otpauth_uri)

    current_user.mfa_secret = secret
    db.commit()

    return StandardResponse(
        success=True,
        data={
            "secret": secret,
            "otpauth_uri": otpauth_uri,
            "qr_code": qr_base64,
        },
        error=None,
    )


@router.post("/mfa/verify", response_model=StandardResponse)
def mfa_verify(
    request: MfaVerifyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.mfa_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA is already enabled",
        )

    if not current_user.mfa_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA setup not initiated. Call /mfa/setup first.",
        )

    if not verify_totp(current_user.mfa_secret, request.code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid MFA code",
        )

    current_user.mfa_enabled = True
    db.commit()

    log_event(
        db=db,
        user_id=current_user.id,
        action=AUDIT_ACTIONS["AUTH_MFA_ENABLED"],
        entity_type="user",
        entity_id=current_user.id,
        status="success",
    )

    return StandardResponse(
        success=True,
        data={"message": "MFA enabled successfully"},
        error=None,
    )


@router.post("/mfa/login", response_model=StandardResponse)
def mfa_login(
    request: MfaLoginRequest,
    req: Request,
    db: Session = Depends(get_db),
):
    mfa_payload = decode_mfa_token(request.mfa_token)
    if mfa_payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired MFA token",
        )

    user_id = mfa_payload.get("sub")
    user = db.query(User).filter(User.user_id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    if not user.mfa_enabled or not user.mfa_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA is not enabled for this account",
        )

    if not verify_totp(user.mfa_secret, request.code):
        client_info = get_client_info(req)
        log_event(
            db=db,
            user_id=user.id,
            action=AUDIT_ACTIONS["AUTH_LOGIN_FAILED"],
            details="Invalid MFA code during login",
            entity_type="user",
            entity_id=user.id,
            status="failure",
            **client_info,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid MFA code",
        )

    user.last_login_at = datetime.now(timezone.utc)
    db.commit()

    token = create_access_token(
        user_id=str(user.user_id),
        role=user.role.name,
        email=user.email,
        full_name=user.full_name,
        claims=AppConstants.ROLE_CLAIMS.get(user.role.name, []),
    )

    client_info = get_client_info(req)
    log_event(
        db=db,
        user_id=user.id,
        action=AUDIT_ACTIONS["AUTH_LOGIN_SUCCESS"],
        details="MFA login completed",
        entity_type="user",
        entity_id=user.id,
        status="success",
        **client_info,
    )

    return StandardResponse(
        success=True,
        data={
            "access_token": token,
            "token_type": "bearer",
            "user": {
                "user_id": str(user.user_id),
                "email": user.email,
                "full_name": user.full_name,
                "role": user.role.name,
                "is_active": user.is_active,
            },
        },
        error=None,
    )


@router.post("/mfa/disable", response_model=StandardResponse)
def mfa_disable(
    request: MfaVerifyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.mfa_enabled or not current_user.mfa_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA is not enabled",
        )

    if not verify_totp(current_user.mfa_secret, request.code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid MFA code",
        )

    current_user.mfa_enabled = False
    current_user.mfa_secret = None
    db.commit()

    log_event(
        db=db,
        user_id=current_user.id,
        action=AUDIT_ACTIONS["AUTH_MFA_DISABLED"],
        entity_type="user",
        entity_id=current_user.id,
        status="success",
    )

    return StandardResponse(
        success=True,
        data={"message": "MFA disabled successfully"},
        error=None,
    )
