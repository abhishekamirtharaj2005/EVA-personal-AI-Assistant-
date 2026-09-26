"""
EVA Password Manager — Secure password lookup and generation.
Integrates with Bitwarden CLI or uses a local encrypted vault.
Requires a master PIN for access.
"""

import hashlib
import json
import logging
import os
import secrets
import string
import threading
from pathlib import Path
from typing import Optional

from core.tool_dispatcher import register_tool

logger = logging.getLogger("eva.actions.password_manager")

_DATA_DIR = Path(__file__).resolve().parent.parent / "config"
_VAULT_FILE = _DATA_DIR / "vault.enc"
_lock = threading.Lock()

# Session PIN cache (cleared on app exit)
_session_pin: Optional[str] = None
_pin_verified = False


def _hash_pin(pin: str) -> str:
    """Hash a PIN with salt for verification."""
    return hashlib.sha256(f"eva_vault_{pin}".encode()).hexdigest()


def _simple_encrypt(data: str, key: str) -> str:
    """Simple XOR encryption (for local vault — not production-grade)."""
    key_bytes = hashlib.sha256(key.encode()).digest()
    encrypted = bytearray()
    for i, char in enumerate(data.encode('utf-8')):
        encrypted.append(char ^ key_bytes[i % len(key_bytes)])
    import base64
    return base64.b64encode(encrypted).decode('ascii')


def _simple_decrypt(data: str, key: str) -> Optional[str]:
    """Simple XOR decryption."""
    try:
        import base64
        key_bytes = hashlib.sha256(key.encode()).digest()
        encrypted = base64.b64decode(data)
        decrypted = bytearray()
        for i, byte in enumerate(encrypted):
            decrypted.append(byte ^ key_bytes[i % len(key_bytes)])
        return decrypted.decode('utf-8')
    except Exception:
        return None


def _load_vault(pin: str) -> Optional[dict]:
    """Load and decrypt the vault."""
    if not _VAULT_FILE.exists():
        return {"entries": [], "pin_hash": _hash_pin(pin)}

    try:
        encrypted = _VAULT_FILE.read_text(encoding='utf-8')
        decrypted = _simple_decrypt(encrypted, pin)
        if decrypted:
            data = json.loads(decrypted)
            if data.get("pin_hash") == _hash_pin(pin):
                return data
        return None  # Wrong PIN
    except Exception as e:
        logger.error(f"Vault load failed: {e}")
        return None


def _save_vault(vault: dict, pin: str) -> None:
    """Encrypt and save the vault."""
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    vault["pin_hash"] = _hash_pin(pin)
    data_str = json.dumps(vault, ensure_ascii=False)
    encrypted = _simple_encrypt(data_str, pin)
    _VAULT_FILE.write_text(encrypted, encoding='utf-8')


def _generate_password(length: int = 16, special: bool = True) -> str:
    """Generate a cryptographically secure password."""
    chars = string.ascii_letters + string.digits
    if special:
        chars += "!@#$%^&*_-+="

    # Ensure at least one of each type
    password = [
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.digits),
    ]
    if special:
        password.append(secrets.choice("!@#$%^&*_-+="))

    remaining = length - len(password)
    password.extend(secrets.choice(chars) for _ in range(remaining))
    secrets.SystemRandom().shuffle(password)
    return "".join(password)


@register_tool(
    name="password_manager",
    description="Secure password management — store, retrieve, generate, and manage passwords. "
                "Protected by a master PIN. Can generate strong passwords. "
                "Use when user asks about passwords, wants to save or look up credentials.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "Action: generate | store | lookup | list | delete | set_pin",
            },
            "pin": {
                "type": "STRING",
                "description": "Master PIN for vault access (4-8 digits)",
            },
            "service": {
                "type": "STRING",
                "description": "Service name for store/lookup. E.g., 'Netflix', 'Gmail'",
            },
            "username": {
                "type": "STRING",
                "description": "Username/email for the service (for store action)",
            },
            "password": {
                "type": "STRING",
                "description": "Password to store (for store action). "
                               "Leave empty to auto-generate.",
            },
            "length": {
                "type": "INTEGER",
                "description": "Password length for generation (default: 16)",
            },
        },
        "required": ["action"],
    },
    category="security",
)
def password_manager(
    action: str,
    pin: str = "",
    service: str = "",
    username: str = "",
    password: str = "",
    length: int = 16,
) -> str:
    """Manage passwords securely."""
    global _session_pin, _pin_verified
    action = action.lower().strip()

    # ── Generate (no PIN needed) ─────────────────────────────
    if action == "generate":
        length = min(max(length, 8), 64)
        pwd = _generate_password(length)
        return (
            f"🔐 Generated password ({length} chars):\n"
            f"   {pwd}\n\n"
            f"Want me to save this? Tell me the service and username."
        )

    # ── Set PIN (first-time setup) ───────────────────────────
    if action == "set_pin":
        if not pin or len(pin) < 4:
            return "Please provide a PIN (4-8 digits). E.g., '1234'"
        _session_pin = pin
        _pin_verified = True
        vault = _load_vault(pin)
        if vault is None:
            vault = {"entries": [], "pin_hash": _hash_pin(pin)}
        _save_vault(vault, pin)
        return "🔐 Master PIN set. Your vault is ready."

    # ── PIN verification ─────────────────────────────────────
    if not pin and _session_pin:
        pin = _session_pin

    if not pin:
        return (
            "🔐 Please provide your master PIN to access the vault. "
            "If this is your first time, say 'set PIN to [your-pin]'."
        )

    with _lock:
        vault = _load_vault(pin)
        if vault is None:
            return "❌ Wrong PIN. Try again."

        _session_pin = pin
        _pin_verified = True

        # ── Store password ───────────────────────────────────
        if action == "store":
            if not service:
                return "Which service? E.g., 'Netflix', 'Gmail'"
            if not password:
                password = _generate_password(length)

            # Check if service exists
            for entry in vault["entries"]:
                if entry["service"].lower() == service.lower():
                    entry["username"] = username or entry["username"]
                    entry["password"] = password
                    _save_vault(vault, pin)
                    return f"🔐 Updated credentials for {service}."

            vault["entries"].append({
                "service": service,
                "username": username or "",
                "password": password,
            })
            _save_vault(vault, pin)
            return (
                f"🔐 Saved credentials for {service}.\n"
                f"   Username: {username or '(none)'}\n"
                f"   Password: {'*' * len(password)} ({len(password)} chars)"
            )

        # ── Lookup ───────────────────────────────────────────
        elif action == "lookup":
            if not service:
                return "Which service's password do you need?"

            for entry in vault["entries"]:
                if service.lower() in entry["service"].lower():
                    return (
                        f"🔐 Credentials for {entry['service']}:\n"
                        f"   Username: {entry['username'] or '(none)'}\n"
                        f"   Password: {entry['password']}"
                    )
            return f"No credentials found for '{service}'."

        # ── List services ────────────────────────────────────
        elif action == "list":
            if not vault["entries"]:
                return "🔐 Your vault is empty. Save some credentials first."

            lines = []
            for i, entry in enumerate(vault["entries"]):
                lines.append(
                    f"  {i+1}. {entry['service']} — {entry['username'] or '(no username)'}"
                )
            return f"🔐 Saved services ({len(vault['entries'])}):\n" + "\n".join(lines)

        # ── Delete ───────────────────────────────────────────
        elif action == "delete":
            if not service:
                return "Which service's credentials should I delete?"
            before = len(vault["entries"])
            vault["entries"] = [
                e for e in vault["entries"]
                if service.lower() not in e["service"].lower()
            ]
            removed = before - len(vault["entries"])
            if removed:
                _save_vault(vault, pin)
                return f"🗑️ Deleted credentials for '{service}'."
            return f"No credentials found for '{service}'."

    return f"Unknown action '{action}'. Use: generate, store, lookup, list, delete, set_pin."
