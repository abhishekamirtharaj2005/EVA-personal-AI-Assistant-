"""
EVA Crypto Utilities
AES-CBC encryption/decryption, session key management, self-signed TLS cert generation.
"""

import base64
import hashlib
import os
import secrets
import string
import time
from pathlib import Path
from typing import Optional

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding as sym_padding
from cryptography.hazmat.backends import default_backend
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
import datetime


_CERT_DIR = Path(__file__).resolve().parent.parent / "config" / "certs"


# ── AES-CBC Encryption ─────────────────────────────────────────

def derive_aes_key(passphrase: str) -> bytes:
    """Derive a 256-bit AES key from a passphrase via SHA-256."""
    return hashlib.sha256(passphrase.encode("utf-8")).digest()


def aes_encrypt(plaintext: str, key: bytes) -> str:
    """
    AES-256-CBC encrypt, return base64(iv + ciphertext).
    Compatible with crypto-js AES on the client side.
    """
    iv = os.urandom(16)
    padder = sym_padding.PKCS7(128).padder()
    padded = padder.update(plaintext.encode("utf-8")) + padder.finalize()
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(padded) + encryptor.finalize()
    return base64.b64encode(iv + ciphertext).decode("utf-8")


def aes_decrypt(encoded: str, key: bytes) -> str:
    """
    AES-256-CBC decrypt from base64(iv + ciphertext).
    """
    raw = base64.b64decode(encoded)
    iv = raw[:16]
    ciphertext = raw[16:]
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    padded = decryptor.update(ciphertext) + decryptor.finalize()
    unpadder = sym_padding.PKCS7(128).unpadder()
    plaintext = unpadder.update(padded) + unpadder.finalize()
    return plaintext.decode("utf-8")


# ── Session Key Management ──────────────────────────────────────

class PairingKeyManager:
    """Manages short-lived pairing keys for the remote dashboard."""

    def __init__(self) -> None:
        self._keys: dict[str, dict] = {}  # key_str -> {aes_key, expires_at, devices}

    def new_key(self, expiry_secs: int = 600) -> str:
        """Generate a new short-lived pairing key."""
        key_str = "".join(
            secrets.choice(string.ascii_uppercase + string.digits)
            for _ in range(6)
        )
        aes_key = derive_aes_key(key_str)
        self._keys[key_str] = {
            "aes_key": aes_key,
            "expires_at": time.time() + expiry_secs,
            "devices": [],
        }
        # Purge expired keys
        self._purge_expired()
        return key_str

    def validate_key(self, key_str: str) -> Optional[bytes]:
        """
        Validate a pairing key. Returns the AES key bytes if valid,
        None if expired or unknown.
        """
        self._purge_expired()
        entry = self._keys.get(key_str)
        if entry is None:
            return None
        if time.time() > entry["expires_at"]:
            del self._keys[key_str]
            return None
        return entry["aes_key"]

    def register_device(self, key_str: str, device_id: str) -> bool:
        """Register a device under a pairing key."""
        entry = self._keys.get(key_str)
        if entry is None:
            return False
        if device_id not in entry["devices"]:
            entry["devices"].append(device_id)
        return True

    def revoke_all(self) -> int:
        """Revoke all active keys. Returns count revoked."""
        count = len(self._keys)
        self._keys.clear()
        return count

    def _purge_expired(self) -> None:
        now = time.time()
        expired = [k for k, v in self._keys.items() if now > v["expires_at"]]
        for k in expired:
            del self._keys[k]


# ── Self-Signed TLS Certificate ─────────────────────────────────

def ensure_self_signed_cert() -> tuple[Path, Path]:
    """
    Generate a self-signed TLS cert + key if they don't exist.
    Returns (cert_path, key_path).
    """
    _CERT_DIR.mkdir(parents=True, exist_ok=True)
    cert_path = _CERT_DIR / "server.crt"
    key_path = _CERT_DIR / "server.key"

    if cert_path.exists() and key_path.exists():
        return cert_path, key_path

    # Generate RSA key
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend(),
    )

    # Build certificate
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "EVA Local Dashboard"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "EVA Assistant"),
    ])

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.utcnow())
        .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=365))
        .add_extension(
            x509.SubjectAlternativeName([
                x509.DNSName("localhost"),
                x509.IPAddress(
                    __import__("ipaddress").IPv4Address("127.0.0.1")
                ),
            ]),
            critical=False,
        )
        .sign(private_key, hashes.SHA256(), default_backend())
    )

    # Write to disk
    with open(key_path, "wb") as f:
        f.write(private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ))

    with open(cert_path, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))

    return cert_path, key_path
