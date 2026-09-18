from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text
from sqlalchemy.sql import func
from database.connection import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)

    # User Info
    user_id = Column(Integer, nullable=False)

    # Transaction Details
    amount = Column(Float, nullable=False)
    location = Column(String(100), nullable=False)
    merchant = Column(String(100), nullable=True)
    transaction_type = Column(String(50), nullable=True)

    # Additional Risk Factors
    hour = Column(Integer, nullable=True)
    is_new_device = Column(Boolean, default=False)
    transactions_today = Column(Integer, default=0)

    # Fraud Analysis
    fraud_probability = Column(Float, default=0.0)
    risk_level = Column(String(20), default="Low")

    # APPROVED | REVIEW | BLOCKED
    status = Column(String(20), default="APPROVED")

    # Explain why transaction was flagged
    fraud_reason = Column(Text, nullable=True)

    # Audit Fields
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class OTPStore(Base):
    __tablename__ = "otp_store"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(100), nullable=False)
    otp_code = Column(String(10), nullable=False)
    purpose = Column(String(30), nullable=False)  # 'verify', 'reset'
    is_used = Column(Boolean, default=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
