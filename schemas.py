"""
Shared Pydantic schemas. Every endpoint in every section returns APIResponse.
This is what keeps the frontend from having to special-case each section's JSON shape.

MERGE NOTE: Sections A, B, and C each extended this file independently. This is
the reconciled version — nothing below is a redesign, it's the union of what all
three sections already built. See MERGE_NOTES.md for details.
"""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, EmailStr


class APIResponse(BaseModel):
    status: str            # "success" | "error"  -- use these exact strings, nothing else
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
    credential: dict  # raw credential JSON from the browser's navigator.credentials.create()


class WebAuthnLoginOptionsRequest(BaseModel):
    email: EmailStr


class WebAuthnLoginVerifyRequest(BaseModel):
    email: EmailStr
    credential: dict  # raw credential JSON from navigator.credentials.get()
    device_fingerprint: Optional[str] = None


# --- Section B: QR cross-device login ---

class QrGenerateRequest(BaseModel):
    device_fingerprint: Optional[str] = None  # the UNTRUSTED device requesting the QR


class QrApproveRequest(BaseModel):
    token: str
    email: EmailStr  # the ALREADY-LOGGED-IN phone/device approving, identifies which user


# --- Section B: step-up auth (extra OTP check for sensitive actions) ---

class StepUpVerifyRequest(BaseModel):
    email: EmailStr
    code: str
