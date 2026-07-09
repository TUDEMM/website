"""Shared helpers for the TUDEMM store: catalog lookup + signed download tokens.

Security model:
  - Prices and file keys live ONLY on the server (data/products.json). The
    browser never sends a price — only a product id — so a malicious user
    cannot tamper with the amount charged.
  - Download links are HMAC-signed tokens that expire, so a paid file URL
    cannot be guessed, forged, or shared indefinitely.
"""
import base64
import hashlib
import hmac
import json
import os
import time
import urllib.request
from pathlib import Path

# data/products.json lives at the project root, two levels up from this file.
_ROOT = Path(__file__).resolve().parents[2]
_CATALOG_PATH = _ROOT / "data" / "products.json"

DOWNLOAD_SECRET = os.environ.get("DOWNLOAD_SECRET", "")
# Default link lifetime: 24 hours (in seconds).
DOWNLOAD_TTL = int(os.environ.get("DOWNLOAD_TTL_SECONDS", "86400"))


def load_catalog():
    with open(_CATALOG_PATH) as f:
        return json.load(f)


def get_product(product_id):
    """Return the server-trusted product dict, or None if not found."""
    catalog = load_catalog()
    for p in catalog.get("products", []):
        if p["id"] == product_id:
            return p
    return None


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _b64url_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def make_download_token(product_id: str, expires_at: int | None = None) -> str:
    """Create a signed, expiring token: base64(payload).base64(hmac)."""
    if not DOWNLOAD_SECRET:
        raise RuntimeError("DOWNLOAD_SECRET is not configured.")
    if expires_at is None:
        expires_at = int(time.time()) + DOWNLOAD_TTL
    payload = json.dumps({"pid": product_id, "exp": expires_at}, separators=(",", ":")).encode()
    sig = hmac.new(DOWNLOAD_SECRET.encode(), payload, hashlib.sha256).digest()
    return f"{_b64url(payload)}.{_b64url(sig)}"


def verify_download_token(token: str):
    """Return (product_id) if valid and unexpired, else None."""
    if not DOWNLOAD_SECRET or not token or "." not in token:
        return None
    try:
        payload_b64, sig_b64 = token.split(".", 1)
        payload = _b64url_decode(payload_b64)
        expected = hmac.new(DOWNLOAD_SECRET.encode(), payload, hashlib.sha256).digest()
        if not hmac.compare_digest(expected, _b64url_decode(sig_b64)):
            return None
        data = json.loads(payload)
        if int(data.get("exp", 0)) < int(time.time()):
            return None
        return data.get("pid")
    except Exception:
        return None


# --- Fulfillment: deliver the secure download link by email --------------------
# Shared by BOTH the Stripe webhook and the PayPal capture, so every paid order
# is delivered exactly the same way regardless of which payment method was used.

SITE_URL = os.environ.get("SITE_URL", "https://tudemm.com").rstrip("/")
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
FROM_ADDR = os.environ.get("CONTACT_FROM", "TUDEMM <onboarding@resend.dev>")


def deliver_download_email(to_email: str, product: dict) -> bool:
    """Mint a fresh expiring token and email the buyer their download link.

    Returns True on a successful send. Safe to call from any payment provider.
    """
    if not RESEND_API_KEY or not to_email or not product:
        return False
    token = make_download_token(product["id"])
    link = f"{SITE_URL}/api/download?token={token}"
    name = product["name"]
    text = (
        f"Thank you for your purchase from TUDEMM!\n\n"
        f"Your e-book: {name}\n\n"
        f"Download it here (link expires in 24 hours):\n{link}\n\n"
        f"If your link expires, just reply to this email and we'll send a fresh one.\n"
        f"\u2014 TUDEMM LLC"
    )
    html = (
        f"<h2>Thank you for your purchase!</h2>"
        f"<p>Your e-book: <strong>{name}</strong></p>"
        f"<p><a href='{link}' style='background:#c4562e;color:#fff;padding:12px 22px;"
        f"border-radius:8px;text-decoration:none;display:inline-block'>Download your e-book</a></p>"
        f"<p style='color:#666;font-size:13px'>This link expires in 24 hours. "
        f"If it expires, reply to this email and we'll send a fresh one.</p>"
        f"<p>\u2014 TUDEMM LLC</p>"
    )
    body = {
        "from": FROM_ADDR, "to": [to_email],
        "subject": f"Your e-book: {name}",
        "text": text, "html": html,
    }
    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return 200 <= resp.status < 300
    except Exception:
        return False
