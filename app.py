"""
FraudShield - AI-Powered Fraud Detection System
FastAPI Backend with JWT Auth, OTP Verification, ML Prediction
+ Real-Time WebSocket feed for live transaction streaming
"""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import os

from database.connection import init_db
from routers import auth, transaction
from routers import websocket as ws_router
from ml.fraud_model import load_model

app = FastAPI(
    title="FraudShield API",
    description="AI-Powered Fraud Detection System with Real-Time Monitoring",
    version="2.0.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Routers
app.include_router(auth.router)
app.include_router(transaction.router)
app.include_router(ws_router.router)   # ← Real-time WebSocket


@app.on_event("startup")
async def startup():
    print("🚀 FraudShield starting up...")
    init_db()
    try:
        load_model()
        print("✅ ML model ready.")
    except Exception as e:
        print(f"⚠️  ML model load warning: {e} — will train on first prediction.")
    print("📡 Real-time WebSocket feed active at /ws/dashboard")


@app.get("/api/health")
async def health():
    from realtime import manager
    return {
        "status": "ok",
        "app": "FraudShield",
        "version": "2.0.0",
        "websocket_clients": manager.connection_count,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
