"""
Shared SQLAlchemy models — reconciled version combining Section A, B, and C features.

Ownership (who WRITES to each table — see CONTRACT.md section 3 comments):
  users                   -> shared (A: locked_until, B: is_verified, C: role)
  credentials             -> Section B owns writes, others may read
  devices                 -> Section A owns writes, others read
  sessions                -> Section C owns writes; everyone else reads via lib/session_utils.py only
  login_history           -> Section C owns write function (log_login_attempt)
  otp_codes               -> Section B owns
  login_tokens            -> Section B owns (QR cross-device sync)
  email_verification_codes-> Section B owns (Registration email confirmation)
  recovery_codes          -> Section B owns (Emergency backup codes)
  step_up_challenges      -> Section A owns (Transaction-bound step-up authentication)
  co_signers / co_signer_credentials / co_signer_approval_requests -> Round 2, delegated auth
"""

import uuid
from datetime import datetime

from sqlalchemy import Column, String, Boolean, DateTime, Integer, ForeignKey, LargeBinary
from sqlalchemy.orm import relationship

from database import Base


def gen_uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=gen_uuid)
    email = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=True)
    is_verified = Column(Boolean, default=False)
    locked_until = Column(DateTime, nullable=True)  # Section A lockout timestamp
    # Section C, item 1 -- "user" or "admin". Never settable through any API
    # endpoint; only ever changed by direct SQL against the database.
    role = Column(String, nullable=False, default="user")
    created_at = Column(DateTime, default=datetime.utcnow)

    credentials = relationship("Credential", back_populates="user", cascade="all, delete-orphan")
    devices = relationship("Device", back_populates="user", cascade="all, delete-orphan")
    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")
    login_history = relationship("LoginHistory", back_populates="user")
    otp_codes = relationship("OTPCode", back_populates="user", cascade="all, delete-orphan")
    recovery_codes = relationship("RecoveryCode", back_populates="user", cascade="all, delete-orphan")
    verification_codes = relationship("EmailVerificationCode", back_populates="user", cascade="all, delete-orphan")


class Credential(Base):
    __tablename__ = "credentials"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    public_key = Column(LargeBinary, nullable=False)
    webauthn_cred_id = Column(String, unique=True, nullable=False)
    device_label = Column(String, nullable=True)
    counter = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_used_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="credentials")


class Device(Base):
    __tablename__ = "devices"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    fingerprint = Column(String, nullable=False)
    trusted = Column(Boolean, default=False)
    first_seen_at = Column(DateTime, default=datetime.utcnow)
    last_seen_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="devices")


class Session(Base):
    __tablename__ = "sessions"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    device_id = Column(String, ForeignKey("devices.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    revoked = Column(Boolean, default=False)

    user = relationship("User", back_populates="sessions")


class LoginHistory(Base):
    __tablename__ = "login_history"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=True)
    method = Column(String, nullable=False)  # "webauthn" | "otp" | "qr" | "recovery_code"
    success = Column(Boolean, nullable=False)
    # Section C, item 3 — this column now holds a KEYED HASH of the IP
    # (see lib/ip_utils.py:hash_ip), never the raw address. Kept the same
    # column name/type rather than renaming, so nothing else that reads
    # login_history needs to change — only what gets WRITTEN here changed.
    ip_address = Column(String, nullable=True)
    # Section C, item 3 — resolved once at write time from the raw IP
    # (before it's discarded), so the app still has a human-readable rough
    # location without ever persisting the exact address. Both nullable:
    # local/private IPs (dev, testing) and geolocation-service failures both
    # legitimately produce no location — that's expected, not an error.
    city = Column(String, nullable=True)
    country = Column(String, nullable=True)
    device_info = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="login_history")


class OTPCode(Base):
    __tablename__ = "otp_codes"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    code_hash = Column(String, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="otp_codes")


class LoginToken(Base):
    """QR cross-device login handoff — Section B owns."""
    __tablename__ = "login_tokens"

    id = Column(String, primary_key=True, default=gen_uuid)
    token = Column(String, unique=True, nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=True)
    status = Column(String, nullable=False, default="pending")  # pending | approved | expired | denied
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)


class EmailVerificationCode(Base):
    """Email registration verification codes — Section B owns."""
    __tablename__ = "email_verification_codes"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    code_hash = Column(String, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="verification_codes")


class RecoveryCode(Base):
    """Backup recovery codes table — Section B owns."""
    __tablename__ = "recovery_codes"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    code_hash = Column(String, nullable=False)
    used = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    used_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="recovery_codes")


class StepUpChallenge(Base):
    """Transaction-bound step-up challenge table — Section A owns."""
    __tablename__ = "step_up_challenges"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    transaction_hash = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False)


# --- Round 2: Assisted "Co-Signer" passkeys (delegated authentication) ---
# For elderly/vulnerable users -- a linked family member's passkey, with no
# login account of their own, used only to approve high-risk actions
# (large transfers, new payees) on the primary user's behalf.

class CoSigner(Base):
    """A registered family member/co-signer for a primary user's account.
    No email/password login of their own -- identified only by their
    registered WebAuthn passkey. Owned by whoever builds this feature."""
    __tablename__ = "co_signers"

    id = Column(String, primary_key=True, default=gen_uuid)
    primary_user_id = Column(String, ForeignKey("users.id"), nullable=False)
    label = Column(String, nullable=True)  # e.g. "My daughter Priya"
    notify_email = Column(String, nullable=False)
    invite_token = Column(String, unique=True, nullable=True)  # cleared once used
    invite_expires_at = Column(DateTime, nullable=True)
    registered = Column(Boolean, default=False)  # True once passkey setup is complete
    created_at = Column(DateTime, default=datetime.utcnow)

    primary_user = relationship("User")
    credentials = relationship("CoSignerCredential", back_populates="co_signer", cascade="all, delete-orphan")


class CoSignerCredential(Base):
    """The co-signer's registered WebAuthn passkey."""
    __tablename__ = "co_signer_credentials"

    id = Column(String, primary_key=True, default=gen_uuid)
    co_signer_id = Column(String, ForeignKey("co_signers.id"), nullable=False)
    public_key = Column(LargeBinary, nullable=False)
    webauthn_cred_id = Column(String, unique=True, nullable=False)
    counter = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    co_signer = relationship("CoSigner", back_populates="credentials")


class CoSignerApprovalRequest(Base):
    """One pending/resolved approval request, bound to the same
    transaction_hash as a StepUpChallenge. The transaction may only proceed
    once BOTH the primary user's step-up (StepUpChallenge.used) AND this
    request's status are satisfied."""
    __tablename__ = "co_signer_approval_requests"

    id = Column(String, primary_key=True, default=gen_uuid)
    primary_user_id = Column(String, ForeignKey("users.id"), nullable=False)
    co_signer_id = Column(String, ForeignKey("co_signers.id"), nullable=False)
    transaction_hash = Column(String, nullable=False)
    status = Column(String, default="pending")  # pending | approved | denied | expired
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    resolved_at = Column(DateTime, nullable=True)


# ==========================================================================
# FINTECH & COMMERCE EXTENSION MODELS (UPI, Lending, Gold, Escrow, Merchant)
# ==========================================================================

class UPITransaction(Base):
    """UPI 2.0 Biometric Passkey Payments & Commerce"""
    __tablename__ = "upi_transactions"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    vpa = Column(String, nullable=False)  # e.g., merchant@okicici
    merchant_name = Column(String, nullable=False)
    amount = Column(Integer, nullable=False)  # in INR
    app_used = Column(String, default="Google Pay")  # Google Pay | PhonePe | Paytm | BHIM
    biometric_verified = Column(Boolean, default=True)
    tx_hash = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")


class CreditLine(Base):
    """Instant Micro-Lending & Vault Trust Credit Health"""
    __tablename__ = "credit_lines"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), unique=True, nullable=False)
    credit_score = Column(Integer, default=785)
    total_limit = Column(Integer, default=50000)
    used_amount = Column(Integer, default=0)
    status = Column(String, default="active")
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")


class MicroLoan(Base):
    """1-Click Emergency Micro-Loans"""
    __tablename__ = "micro_loans"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    loan_amount = Column(Integer, nullable=False)
    tenure_months = Column(Integer, default=6)
    monthly_emi = Column(Integer, nullable=False)
    status = Column(String, default="disbursed")  # disbursed | repaid
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")


class GoldVault(Base):
    """Spare-Change Round-Up & 24K Digital Gold Investing"""
    __tablename__ = "gold_vaults"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), unique=True, nullable=False)
    gold_grams = Column(Integer, default=342)  # 3.42 grams * 100
    total_invested = Column(Integer, default=24500)
    roundup_enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")


class EscrowDeal(Base):
    """Biometric Co-Signed Escrow Commerce Deals"""
    __tablename__ = "escrow_deals"

    id = Column(String, primary_key=True, default=gen_uuid)
    buyer_id = Column(String, ForeignKey("users.id"), nullable=False)
    seller_email = Column(String, nullable=False)
    item_title = Column(String, nullable=False)
    amount = Column(Integer, nullable=False)
    status = Column(String, default="locked")  # locked | buyer_approved | seller_approved | released
    created_at = Column(DateTime, default=datetime.utcnow)

    buyer = relationship("User")


class MerchantInvoice(Base):
    """1-Click Digital Invoices & Commerce Analytics"""
    __tablename__ = "merchant_invoices"

    id = Column(String, primary_key=True, default=gen_uuid)
    merchant_id = Column(String, ForeignKey("users.id"), nullable=False)
    client_name = Column(String, nullable=False)
    client_email = Column(String, nullable=False)
    amount = Column(Integer, nullable=False)
    item_description = Column(String, nullable=False)
    status = Column(String, default="unpaid")  # unpaid | paid
    payment_link = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    merchant = relationship("User")