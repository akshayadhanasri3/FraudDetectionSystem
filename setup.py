#!/usr/bin/env python3
"""
FraudShield Setup Script
Trains the ML model and initializes the database.
Run this once before starting the server.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

print("=" * 50)
print("  FraudShield — Setup Script")
print("=" * 50)

# 1. Train the ML Model
print("\n[1/2] Training ML Model...")
from ml.fraud_model import train_model
train_model()

# 2. Initialize Database
print("\n[2/2] Initializing Database...")
try:
    from database.connection import init_db
    init_db()
    print("✅ Database initialized.")
except Exception as e:
    print(f"⚠️  Database setup failed: {e}")
    print("   Make sure MySQL/PostgreSQL is running and .env is configured.")
    print("   You can still run the app — tables will be created on first start.")

print("\n✅ Setup complete! Run the server with:")
print("   uvicorn app:app --reload --host 0.0.0.0 --port 8000")
print("\n   Then open: http://localhost:8000")
