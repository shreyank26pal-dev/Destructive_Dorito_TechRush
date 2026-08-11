"""
Shared Pydantic schemas — reconciled union of Section A, Section B, and Section C.
Every endpoint in every section returns APIResponse.
"""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, EmailStr


class APIResponse(BaseModel):
    status: str            # "success" | "error"
    data: Optional[Any] = None
    message: Optional[str] = None


def success_response(data: Any = None, message: str = None) -> dict:
    """Helper so every section builds success responses identically."""
    return APIResponse(status="success", data=data, message=message).model_dump()


def error_response(message: str, data: Any = None) -> dict:
    """Helper so every section builds error responses identically."""
    return APIResponse(status="error", data=data, message=message).model_dump()


# --- Section A request bodies ---

class RegisterRequest(BaseModel):
    email: EmailStr
    name: Optional[str] = None


class CheckDeviceRequest(BaseModel):
    user_id: str
    fingerprint: str


# --- Section A / Section C shared response shapes ---

class UserOut(BaseModel):
    id: str
    email: str
    name: Optional[str] = None
    is_verified: Optional[bool] = False

    class Config:
        from_attributes = True


# --- Section C request bodies / response shapes ---

class ProfileUpdateRequest(BaseModel):
    name: Optional[str] = None


class LoginHistoryItem(BaseModel):
    id: str
    method: str
    success: bool
    ip_address: Optional[str] = None
    device_info: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# --- Section B request bodies ---

class OtpSendRequest(BaseModel):
    email: EmailStr


class OtpVerifyRequest(BaseModel):
    email: EmailStr
    code: str
    device_fingerprint: Optional[str] = None


class WebAuthnRegisterVerifyRequest(BaseModel):
    email: EmailStr
    credential: dict


class WebAuthnLoginOptionsRequest(BaseModel):
    email: EmailStr


class WebAuthnLoginVerifyRequest(BaseModel):
    email: EmailStr
    credential: dict
    device_fingerprint: Optional[str] = None


# --- Section B: QR cross-device login ---

class QrGenerateRequest(BaseModel):
    device_fingerprint: Optional[str] = None


class QrApproveRequest(BaseModel):
    token: str
    email: EmailStr


# --- Section B / Section A: step-up auth ---

class StepUpVerifyRequest(BaseModel):
    email: EmailStr
    code: str
    challenge_id: Optional[str] = None


class StepUpChallengeRequest(BaseModel):
    user_id: str
    transaction: dict


# --- Section B: Email Verification & Backup Recovery Codes ---

class EmailVerificationSendRequest(BaseModel):
    email: EmailStr


class EmailVerificationVerifyRequest(BaseModel):
    email: EmailStr
    code: str


class RecoveryCodeGenerateRequest(BaseModel):
    email: EmailStr


class RecoveryCodeVerifyRequest(BaseModel):
    email: EmailStr
    code: str
    device_fingerprint: Optional[str] = None


# --- Round 2: Co-signer (assisted authentication for high-risk actions) ---

class CoSignerInviteRequest(BaseModel):
    primary_user_id: str
    label: Optional[str] = None
    notify_email: EmailStr


class CoSignerRegisterOptionsRequest(BaseModel):
    invite_token: str


class CoSignerRegisterVerifyRequest(BaseModel):
    invite_token: str
    credential: dict


class CoSignerApproveOptionsRequest(BaseModel):
    request_id: str


class CoSignerApproveVerifyRequest(BaseModel):
    request_id: str
    credential: dict