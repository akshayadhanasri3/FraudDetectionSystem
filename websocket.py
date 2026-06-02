"""
WebSocket Router — FraudShield Real-Time Feed
/ws/dashboard  → live transaction events broadcast to all dashboards
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from realtime import manager
from core import decode_token

router = APIRouter()


@router.websocket("/ws/dashboard")
async def ws_dashboard(websocket: WebSocket, token: str = Query(None)):
    """
    Connect to the live transaction feed.
    Pass token=<JWT> as a query param for auth.
    """
    # Optional auth check (skip if no token passed — dev mode)
    if token:
        payload = decode_token(token)
        if not payload or payload.get("type") != "access":
            await websocket.close(code=4001)
            return

    await manager.connect(websocket)
    try:
        # Send initial welcome ping
        await manager.send_personal(websocket, "connected", {
            "message": "Connected to FraudShield Live Feed",
            "active_clients": manager.connection_count,
        })

        # Keep alive — listen for pings from client
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await manager.send_personal(websocket, "pong", {
                    "active_clients": manager.connection_count
                })
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@router.get("/api/ws/status")
async def ws_status():
    """Check how many clients are live."""
    return {
        "active_connections": manager.connection_count,
        "status": "live",
    }
