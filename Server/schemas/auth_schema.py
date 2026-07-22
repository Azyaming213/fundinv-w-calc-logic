from typing import Optional
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field
import appconstants as AppConstants


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RegisterRequest(BaseModel):
    token: str
    password: str = Field(..., min_length=8, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserResponse"


class UserResponse(BaseModel):
    user_id: str
    email: EmailStr
    full_name: str
    role: str
    is_active: bool
    last_login_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8, max_length=128)


class InviteCreateRequest(BaseModel):
    email: EmailStr
    full_name: str
    role: str = AppConstants.ROLES["INVESTOR"]


class MfaVerifyRequest(BaseModel):
    code: str = Field(..., min_length=6, max_length=6)


class MfaLoginRequest(BaseModel):
    mfa_token: str
    code: str = Field(..., min_length=6, max_length=6)


class StandardResponse(BaseModel):
    success: bool
    data: Optional[dict] = None
    error: Optional[dict] = None


TokenResponse.model_rebuild()
