from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from core import send_fraud_alert
from database.connection import get_db
from database.models import Transaction, User
from core import decode_token
from ml.fraud_model import predict_fraud
from realtime import manager   # ← Real-time broadcast

router = APIRouter(prefix="/api", tags=["transactions"])


# ──────────────────────────────────────────────────────────────
# AUTH DEPENDENCY
# ──────────────────────────────────────────────────────────────

def get_current_user(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
) -> User:

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")

    token = authorization.split(" ")[1]

    payload = decode_token(token)

    if not payload or payload.get("type") != "access":
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token"
        )

    user = db.query(User).filter(
        User.id == int(payload["sub"])
    ).first()

    if not user:
        raise HTTPException(
            status_code=401,
            detail="User not found"
        )

    return user


# ──────────────────────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────────────────────

LOCATION_MAP = {
    "Local": 0,
    "Domestic": 0,
    "Foreign": 1,
    "International": 1,
    "Unknown": 1,
}

MERCHANT_VELOCITY = {
    "Grocery": 0.1,
    "Restaurant": 0.1,
    "Shopping": 0.2,
    "Electronics": 0.4,
    "Travel": 0.5,
    "Crypto": 0.8,
    "Unknown": 0.7,
}


# ──────────────────────────────────────────────────────────────
# SCHEMAS
# ──────────────────────────────────────────────────────────────

class TransactionRequest(BaseModel):
    amount: float
    location: str
    merchant: Optional[str] = "Unknown"
    transaction_type: Optional[str] = "Purchase"
    hour: Optional[int] = None
    is_new_device: Optional[int] = 0
    transactions_today: Optional[int] = 1


class TransactionResponse(BaseModel):
    id: int
    amount: float
    location: str
    merchant: str
    status: str
    risk_level: str
    fraud_probability: float
    created_at: datetime

    class Config:
        from_attributes = True


# ──────────────────────────────────────────────────────────────
# ANALYZE TRANSACTION  (with real-time broadcast)
# ──────────────────────────────────────────────────────────────

@router.post("/transactions/analyze")
async def analyze_transaction(
    data: TransactionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):

    hour = (
        data.hour
        if data.hour is not None
        else datetime.now().hour
    )

    is_foreign = LOCATION_MAP.get(data.location, 0)

    velocity = MERCHANT_VELOCITY.get(
        data.merchant,
        0.3
    )

    result = predict_fraud(
        amount=data.amount,
        hour=hour,
        is_foreign=is_foreign,
        is_new_device=data.is_new_device,
        transactions_today=data.transactions_today,
        velocity_score=velocity,
    )

    fraud_probability = result["fraud_probability"]

    reasons = []

    if data.amount > 10000:
        reasons.append("High Transaction Amount")

    if is_foreign:
        reasons.append("Foreign Location")

    if data.is_new_device:
        reasons.append("New Device Detected")

    if hour >= 22 or hour <= 5:
        reasons.append("Late Night Transaction")

    if data.transactions_today > 10:
        reasons.append("Unusual Transaction Frequency")

    # Risk Decision

    if fraud_probability >= 80:
        status = "BLOCKED"
        risk_level = "High"

    elif fraud_probability >= 50:
        status = "REVIEW"
        risk_level = "Medium"

    else:
        status = "APPROVED"
        risk_level = "Low"

    txn = Transaction(
        user_id=current_user.id,
        amount=data.amount,
        location=data.location,
        merchant=data.merchant or "Unknown",
        transaction_type=data.transaction_type or "Purchase",

        hour=hour,
        is_new_device=bool(data.is_new_device),
        transactions_today=data.transactions_today,

        fraud_probability=fraud_probability,
        risk_level=risk_level,
        status=status,

        fraud_reason=", ".join(reasons)
    )
    
    
    
    db.add(txn)
    db.commit()
    db.refresh(txn)

    if status == "BLOCKED":
        try:
            await send_fraud_alert(
                to_email=current_user.email,
                amount=data.amount,
                probability=fraud_probability / 100
            )
            print(f"🚨 Fraud alert email sent to {current_user.email}")
        except Exception as e:
            print(f"❌ Failed to send fraud alert email: {e}")

    response_data = {
        "transaction_id": txn.id,
        "amount": txn.amount,
        "location": txn.location,
        "merchant": txn.merchant,
        "transaction_type": txn.transaction_type,

        "fraud_probability": fraud_probability,
        "risk_level": risk_level,
        "status": status,

        "reasons": reasons,
        "user": current_user.username,

        "message": (
            "🚫 Transaction Blocked"
            if status == "BLOCKED"
            else
            "⚠️ Transaction Under Review"
            if status == "REVIEW"
            else
            "✅ Transaction Approved"
        ),
    }

    await manager.broadcast("transaction", response_data)

    return response_data
# ──────────────────────────────────────────────────────────────
# GET TRANSACTIONS
# ──────────────────────────────────────────────────────────────

@router.get("/transactions")
async def get_transactions(
    skip: int = 0,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):

    query = db.query(Transaction)

    if not current_user.is_admin:
        query = query.filter(
            Transaction.user_id == current_user.id
        )

    total = query.count()

    transactions = (
        query
        .order_by(Transaction.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    return {
        "total": total,
        "transactions": [
            {
                "id": t.id,
                "amount": t.amount,
                "location": t.location,
                "merchant": t.merchant,
                "transaction_type": t.transaction_type,

                "status": t.status,
                "risk_level": t.risk_level,
                "fraud_probability": t.fraud_probability,

                "fraud_reason": t.fraud_reason,

                "created_at":
                    t.created_at.isoformat()
                    if t.created_at
                    else None,
            }
            for t in transactions
        ],
    }


# ──────────────────────────────────────────────────────────────
# DASHBOARD
# ──────────────────────────────────────────────────────────────

@router.get("/dashboard/stats")
async def dashboard_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):

    query = db.query(Transaction)

    if not current_user.is_admin:
        query = query.filter(
            Transaction.user_id == current_user.id
        )

    total = query.count()

    blocked_count = query.filter(
        Transaction.status == "BLOCKED"
    ).count()

    approved_count = query.filter(
        Transaction.status == "APPROVED"
    ).count()

    review_count = query.filter(
        Transaction.status == "REVIEW"
    ).count()

    total_amount = (
        db.query(func.sum(Transaction.amount))
        .scalar()
        or 0
    )

    fraud_pct = (
        round((blocked_count / total) * 100, 2)
        if total > 0
        else 0
    )

    trend_raw = db.execute(
        text("""
            SELECT DATE(created_at) as day,
                   COUNT(*) as total,
                   SUM(
                        CASE
                            WHEN status='BLOCKED'
                            THEN 1
                            ELSE 0
                        END
                   ) as frauds
            FROM transactions
            GROUP BY DATE(created_at)
            ORDER BY day DESC
            LIMIT 7
        """)
    ).fetchall()

    trend = [
        {
            "day": str(r[0]),
            "total": r[1],
            "frauds": r[2],
        }
        for r in trend_raw
    ]

    return {
        "total_transactions": total,
        "fraud_transactions": blocked_count,
        "safe_transactions": approved_count,
        "review_transactions": review_count,

        "total_amount": round(total_amount, 2),

        "fraud_percentage": fraud_pct,

        "trend": trend,

        "user": {
            "username": current_user.username,
            "email": current_user.email,
            "is_admin": current_user.is_admin,
        },
    }
