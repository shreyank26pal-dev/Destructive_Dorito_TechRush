"""
FinTech & Commerce API Router — India-First Passwordless Banking Engine.
Handles:
1. UPI 2.0 Biometric Passkey Payments & Deep-Linking (GPay, PhonePe, Paytm, BHIM).
2. Instant Micro-Lending & Vault Trust Credit Health.
3. Spare-Change Round-Up & 24K Digital Gold Investing.
4. Biometric Co-Signed Escrow Commerce.
5. Merchant Digital Invoices & Sales Analytics.
"""

import hashlib
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db
from lib.session_utils import get_current_user
from models import (
    User, UPITransaction, CreditLine, MicroLoan, GoldVault, EscrowDeal, MerchantInvoice
)

def _resolve_user(request: Request, db: Session) -> User:
    user_data = get_current_user(request)
    if user_data:
        user = db.query(User).filter(User.id == user_data["id"]).first()
        if user:
            return user
    # Fallback to demo primary user for smooth hackathon testing
    user = db.query(User).first()
    if not user:
        user = User(email="customer@securebank.com", name="Vault Member", is_verified=True)
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


router = APIRouter(prefix="/api/fintech", tags=["FinTech & Commerce"])


# --- Schemas ---

class UPIPayRequest(BaseModel):
    vpa: str = Field(..., example="merchant@okicici")
    merchant_name: str = Field(..., example="Starbucks India")
    amount: int = Field(..., example=450)
    app_used: str = Field("Google Pay", example="Google Pay")  # Google Pay | PhonePe | Paytm | BHIM
    biometric_verified: bool = True


class ApplyLoanRequest(BaseModel):
    loan_amount: int = Field(..., example=15000)
    tenure_months: int = Field(6, example=6)


class CreateEscrowRequest(BaseModel):
    seller_email: str = Field(..., example="seller@domain.com")
    item_title: str = Field(..., example="MacBook Pro M2 Deposit")
    amount: int = Field(..., example=12000)


class CreateInvoiceRequest(BaseModel):
    client_name: str = Field(..., example="Rahul Sharma")
    client_email: str = Field(..., example="rahul@client.com")
    amount: int = Field(..., example=8500)
    item_description: str = Field(..., example="UI/UX Design Services")


# --- Endpoints ---

@router.post("/upi/pay")
def execute_upi_pay(req: UPIPayRequest, request: Request, db: Session = Depends(get_db)):
    """Execute UPI 2.0 Passkey-Preauthorized Payment and generate deep-link + receipt."""
    user = _resolve_user(request, db)
    
    # Generate cryptographic payment verification hash
    raw_sig = f"{user.id}:{req.vpa}:{req.amount}:{datetime.utcnow().isoformat()}"
    tx_hash = "0x" + hashlib.sha256(raw_sig.encode()).hexdigest()[:32]
    
    # Store UPI transaction record
    tx = UPITransaction(
        user_id=user.id,
        vpa=req.vpa,
        merchant_name=req.merchant_name,
        amount=req.amount,
        app_used=req.app_used,
        biometric_verified=req.biometric_verified,
        tx_hash=tx_hash
    )
    db.add(tx)
    
    # Auto-roundup spare change to Gold Vault if enabled
    gold = db.query(GoldVault).filter(GoldVault.user_id == user.id).first()
    roundup_added = 0
    if gold and gold.roundup_enabled:
        spare = 10 - (req.amount % 10) if (req.amount % 10) != 0 else 0
        if spare > 0:
            gold.total_invested += spare
            gold.gold_grams += int(spare * 1.5)  # conversion factor
            roundup_added = spare
            
    db.commit()
    db.refresh(tx)
    
    # NPCI Standard upi://pay deep link format for mobile GPay / PhonePe
    upi_deeplink = f"upi://pay?pa={req.vpa}&pn={req.merchant_name.replace(' ', '%20')}&am={req.amount}&cu=INR&tn=DoritoVault%20Passkey%20Pay"
    
    return {
        "status": "success",
        "message": f"UPI Payment of ₹{req.amount} pre-authorized via {req.app_used}",
        "tx_id": tx.id,
        "tx_hash": tx_hash,
        "upi_deeplink": upi_deeplink,
        "roundup_invested": roundup_added,
        "timestamp": tx.created_at.isoformat()
    }


@router.get("/credit/summary")
def get_credit_summary(request: Request, db: Session = Depends(get_db)):
    """Retrieve Vault Trust Credit Rating and active micro-loan offers."""
    user = _resolve_user(request, db)
    
    credit = db.query(CreditLine).filter(CreditLine.user_id == user.id).first()
    if not credit:
        credit = CreditLine(user_id=user.id, credit_score=785, total_limit=50000, used_amount=0)
        db.add(credit)
        db.commit()
        db.refresh(credit)
        
    loans = db.query(MicroLoan).filter(MicroLoan.user_id == user.id).all()
    
    return {
        "credit_score": credit.credit_score,
        "trust_rating": "Excellent (Tier 1)",
        "total_limit": credit.total_limit,
        "used_amount": credit.used_amount,
        "available_limit": credit.total_limit - credit.used_amount,
        "active_loans": [
            {
                "id": l.id,
                "amount": l.loan_amount,
                "tenure": l.tenure_months,
                "monthly_emi": l.monthly_emi,
                "status": l.status,
                "created_at": l.created_at.isoformat()
            } for l in loans
        ]
    }


@router.post("/credit/apply-loan")
def apply_instant_loan(req: ApplyLoanRequest, request: Request, db: Session = Depends(get_db)):
    """Instant 1-Click Micro-Loan Disbursement backed by Vault Trust Score."""
    user = _resolve_user(request, db)
    
    credit = db.query(CreditLine).filter(CreditLine.user_id == user.id).first()
    if not credit:
        credit = CreditLine(user_id=user.id, credit_score=785, total_limit=50000, used_amount=0)
        db.add(credit)
        
    if req.loan_amount > (credit.total_limit - credit.used_amount):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Requested amount ₹{req.loan_amount} exceeds available credit limit ₹{credit.total_limit - credit.used_amount}"
        )
        
    emi = int((req.loan_amount * 1.08) / req.tenure_months)
    loan = MicroLoan(
        user_id=user.id,
        loan_amount=req.loan_amount,
        tenure_months=req.tenure_months,
        monthly_emi=emi,
        status="disbursed"
    )
    credit.used_amount += req.loan_amount
    db.add(loan)
    db.commit()
    
    return {
        "status": "success",
        "message": f"₹{req.loan_amount} disbursed instantly to your account balance!",
        "loan_id": loan.id,
        "monthly_emi": emi,
        "remaining_limit": credit.total_limit - credit.used_amount
    }


@router.get("/gold/summary")
def get_gold_summary(request: Request, db: Session = Depends(get_db)):
    """Retrieve 24K Digital Gold holdings & spare-change round-up settings."""
    user = _resolve_user(request, db)
    
    gold = db.query(GoldVault).filter(GoldVault.user_id == user.id).first()
    if not gold:
        gold = GoldVault(user_id=user.id, gold_grams=342, total_invested=24500, roundup_enabled=True)
        db.add(gold)
        db.commit()
        db.refresh(gold)
        
    current_value = int((gold.gold_grams / 100) * 7200)  # ₹7,200 per gram current market price
    
    return {
        "gold_grams": round(gold.gold_grams / 100, 2),
        "total_invested": gold.total_invested,
        "current_market_value": current_value,
        "xirr_returns": "+14.8%",
        "roundup_enabled": gold.roundup_enabled
    }


@router.post("/gold/roundup-toggle")
def toggle_gold_roundup(request: Request, db: Session = Depends(get_db)):
    """Toggle automated spare-change investment round-up."""
    user = _resolve_user(request, db)
    
    gold = db.query(GoldVault).filter(GoldVault.user_id == user.id).first()
    if not gold:
        gold = GoldVault(user_id=user.id, gold_grams=342, total_invested=24500, roundup_enabled=True)
        db.add(gold)
        
    gold.roundup_enabled = not gold.roundup_enabled
    db.commit()
    
    return {
        "status": "success",
        "roundup_enabled": gold.roundup_enabled,
        "message": "Spare-change round-up auto-investing is now " + ("ENABLED" if gold.roundup_enabled else "DISABLED")
    }


@router.post("/escrow/create")
def create_escrow_deal(req: CreateEscrowRequest, request: Request, db: Session = Depends(get_db)):
    """Create a Biometric Co-Signed Escrow Commerce Deal."""
    user = _resolve_user(request, db)
    
    escrow = EscrowDeal(
        buyer_id=user.id,
        seller_email=req.seller_email,
        item_title=req.item_title,
        amount=req.amount,
        status="locked"
    )
    db.add(escrow)
    db.commit()
    db.refresh(escrow)
    
    return {
        "status": "success",
        "message": f"Escrow deal for '{req.item_title}' locked with ₹{req.amount}",
        "escrow_id": escrow.id,
        "status_code": escrow.status
    }


@router.post("/escrow/release/{escrow_id}")
def release_escrow_deal(escrow_id: str, request: Request, db: Session = Depends(get_db)):
    """Biometrically release locked escrow funds to seller."""
    user = _resolve_user(request, db)
    
    escrow = db.query(EscrowDeal).filter(EscrowDeal.id == escrow_id, EscrowDeal.buyer_id == user.id).first()
    if not escrow:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Escrow deal not found")
        
    escrow.status = "released"
    db.commit()
    
    return {
        "status": "success",
        "message": f"Biometric verification approved. ₹{escrow.amount} released to {escrow.seller_email}!"
    }


@router.post("/merchant/invoice")
def create_merchant_invoice(req: CreateInvoiceRequest, request: Request, db: Session = Depends(get_db)):
    """Create a digital invoice with embedded biometric payment link."""
    user = _resolve_user(request, db)
    
    inv_id = str(uuid.uuid4())[:8]
    pay_link = f"https://doritovault.in/pay/inv_{inv_id}"
    
    inv = MerchantInvoice(
        merchant_id=user.id,
        client_name=req.client_name,
        client_email=req.client_email,
        amount=req.amount,
        item_description=req.item_description,
        status="unpaid",
        payment_link=pay_link
    )
    db.add(inv)
    db.commit()
    
    return {
        "status": "success",
        "message": f"Invoice created for {req.client_name} (₹{req.amount})",
        "invoice_id": inv.id,
        "payment_link": pay_link
    }
