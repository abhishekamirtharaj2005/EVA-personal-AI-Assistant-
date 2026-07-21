"""
EVA Dashboard Server — FastAPI + WebSocket for remote phone control.
QR pairing, AES-encrypted payloads, phone mic relay.
"""

import asyncio
import json
import logging
import os
import threading
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, Form
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from utils.crypto_utils import PairingKeyManager, aes_encrypt, aes_decrypt
from utils.platform_utils import get_local_ip
from memory.config_manager import config

logger = logging.getLogger("eva.dashboard")

# Module state
_app = FastAPI(title="EVA Remote Dashboard")
_pairing_manager = PairingKeyManager()
_eva_live_ref = None  # Set by main.py after boot
_connected_devices: list[dict] = []
_ws_clients: list[WebSocket] = []

STATIC_DIR = Path(__file__).parent / "static"
UPLOAD_DIR = Path(__file__).parent.parent / "config" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def set_eva_live_ref(eva_live) -> None:
    """Set reference to the EvaLive instance for command injection."""
    global _eva_live_ref
    _eva_live_ref = eva_live


# ── Routes ──────────────────────────────────────────────────────

@_app.get("/login", response_class=HTMLResponse)
async def login_page():
    return FileResponse(STATIC_DIR / "login.html")


@_app.get("/", response_class=HTMLResponse)
async def dashboard_page():
    return FileResponse(STATIC_DIR / "app.html")


@_app.post("/api/device-login")
async def device_login(data: dict):
    """Pairing handshake: validate key, issue session."""
    key = data.get("key", "")
    device_id = data.get("device_id", "unknown")

    aes_key = _pairing_manager.validate_key(key)
    if aes_key is None:
        return JSONResponse({"error": "Invalid or expired key"}, status_code=401)

    _pairing_manager.register_device(key, device_id)
    _connected_devices.append({"device_id": device_id, "key": key})

    logger.info(f"Device paired: {device_id}")
    return {"status": "paired", "session_key": key}


@_app.post("/api/revoke-devices")
async def revoke_devices():
    """Revoke all active sessions."""
    count = _pairing_manager.revoke_all()
    _connected_devices.clear()
    return {"revoked": count}


@_app.post("/api/command")
async def receive_command(data: dict):
    """Inject a text command from the phone/browser."""
    command = data.get("command", "")
    key = data.get("session_key", "")

    if not command:
        return JSONResponse({"error": "Empty command"}, status_code=400)

    # Decrypt if encrypted
    if key:
        aes_key = _pairing_manager.validate_key(key)
        if aes_key:
            try:
                command = aes_decrypt(command, aes_key)
            except Exception:
                pass  # Use as plaintext

    if _eva_live_ref:
        _eva_live_ref.inject_text_command(command)
        return {"status": "sent", "command": command[:50]}

    return JSONResponse({"error": "EVA not connected"}, status_code=503)


@_app.post("/api/wake")
async def remote_wake():
    """Remote wake trigger."""
    if _eva_live_ref:
        _eva_live_ref.inject_text_command("The user has sent a remote wake signal.")
        return {"status": "woke"}
    return JSONResponse({"error": "EVA not connected"}, status_code=503)


@_app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    """Phone → desktop file transfer."""
    save_path = UPLOAD_DIR / file.filename
    content = await file.read()
    save_path.write_bytes(content)
    logger.info(f"File uploaded: {file.filename} ({len(content)} bytes)")

    # Process the file
    if _eva_live_ref:
        _eva_live_ref.inject_text_command(
            f"A file was uploaded from the phone: {save_path}. "
            f"Please process and describe it."
        )

    return {"status": "uploaded", "filename": file.filename}


@_app.get("/api/files")
async def list_files():
    """List uploaded files."""
    files = []
    for f in UPLOAD_DIR.iterdir():
        if f.is_file():
            files.append({
                "name": f.name,
                "size": f.stat().st_size,
                "url": f"/uploads/{f.name}",
            })
    return {"files": files}


@_app.get("/uploads/{filename}")
async def serve_upload(filename: str):
    path = UPLOAD_DIR / filename
    if path.exists():
        return FileResponse(path)
    return JSONResponse({"error": "Not found"}, status_code=404)


# ── WebSocket: Phone Audio ──────────────────────────────────────

@_app.websocket("/ws/phone-audio")
async def phone_audio_ws(websocket: WebSocket):
    """Phone mic → desktop app audio relay."""
    await websocket.accept()
    logger.info("Phone audio WebSocket connected")

    try:
        while True:
            data = await websocket.receive_bytes()
            if _eva_live_ref:
                _eva_live_ref.inject_phone_audio(data)
    except WebSocketDisconnect:
        logger.info("Phone audio WebSocket disconnected")


# ── WebSocket: General State Channel ────────────────────────────

@_app.websocket("/ws")
async def general_ws(websocket: WebSocket):
    """General realtime state channel."""
    await websocket.accept()
    _ws_clients.append(websocket)
    logger.info("WebSocket client connected")

    try:
        while True:
            data = await websocket.receive_text()
            # Handle incoming messages
            try:
                msg = json.loads(data)
                if msg.get("type") == "command" and _eva_live_ref:
                    _eva_live_ref.inject_text_command(msg.get("text", ""))
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        _ws_clients.remove(websocket)
        logger.info("WebSocket client disconnected")


# ── Server Control ──────────────────────────────────────────────

def generate_pairing_key() -> tuple[str, str]:
    """Generate a new pairing key and return (key, connect_url)."""
    key = _pairing_manager.new_key(expiry_secs=600)
    ip = get_local_ip()
    port = config.get("dashboard_port", 8765)
    url = f"https://{ip}:{port}/login?key={key}"
    return key, url


def start_dashboard_server(eva_live=None) -> threading.Thread:
    """Start the dashboard server in a background thread."""
    if eva_live:
        set_eva_live_ref(eva_live)

    port = config.get("dashboard_port", 8765)

    # Generate self-signed certs
    from utils.crypto_utils import ensure_self_signed_cert
    cert_path, key_path = ensure_self_signed_cert()

    def _run():
        uvicorn.run(
            _app,
            host="0.0.0.0",
            port=port,
            ssl_certfile=str(cert_path),
            ssl_keyfile=str(key_path),
            log_level="warning",
        )

    thread = threading.Thread(target=_run, daemon=True, name="eva-dashboard")
    thread.start()
    logger.info(f"Dashboard server started on https://0.0.0.0:{port}")
    return thread


def get_app() -> FastAPI:
    """Return the FastAPI app instance (for testing)."""
    return _app
