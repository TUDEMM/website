"""Vercel Serverless Function: Stripe webhook — fulfillment + email delivery.

Stripe calls this URL after a payment. We verify the signature (so nobody can
fake a "paid" event), then email the buyer a secure, expiring download link for
the e-book they purchased. Delivery uses Resend (already configured for TUDEMM).

Env vars:
  STRIPE_SECRET_KEY        sk_live_... / sk_test_...
  STRIPE_WEBHOOK_SECRET    whsec_... (from the Stripe webhook you create)
  DOWNLOAD_SECRET          any long random string (signs download tokens)
  RESEND_API_KEY           re_... (reused from the contact form)
  CONTACT_FROM             e.g. "TUDEMM <info@tudemm.com>"
  SITE_URL                 e.g. https://tudemm.com
"""
import json
import os
import sys
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib.store import get_product, make_download_token  # noqa: E402

import stripe  # noqa: E402

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")
WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
FROM_ADDR = os.environ.get("CONTACT_FROM", "TUDEMM <onboarding@resend.dev>")
SITE_URL = os.environ.get("SITE_URL", "https://tudemm.com").rstrip("/")


def _email_download_link(to_email, product, link):
    if not RESEND_API_KEY:
        return False
    name = product["name"]
    text = (
        f"Thank you for your purchase from TUDEMM!\n\n"
        f"Your e-book: {name}\n\n"
        f"Download it here (link expires in 24 hours):\n{link}\n\n"
        f"If your link expires, just reply to this email and we'll send a fresh one.\n"
        f"— TUDEMM LLC"
    )
    html = (
        f"<h2>Thank you for your purchase!</h2>"
        f"<p>Your e-book: <strong>{name}</strong></p>"
        f"<p><a href='{link}' style='background:#c4562e;color:#fff;padding:12px 22px;"
        f"border-radius:8px;text-decoration:none;display:inline-block'>Download your e-book</a></p>"
        f"<p style='color:#666;font-size:13px'>This link expires in 24 hours. "
        f"If it expires, reply to this email and we'll send a fresh one.</p>"
        f"<p>— TUDEMM LLC</p>"
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


class handler(BaseHTTPRequestHandler):
    def _respond(self, status, obj):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(obj).encode("utf-8"))

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        payload = self.rfile.read(length)
        sig = self.headers.get("Stripe-Signature", "")

        # Verify the event really came from Stripe.
        try:
            event = stripe.Webhook.construct_event(payload, sig, WEBHOOK_SECRET)
        except Exception:
            return self._respond(400, {"error": "Invalid signature."})

        if event["type"] == "checkout.session.completed":
            session = event["data"]["object"]
            product_id = (session.get("metadata") or {}).get("product_id")
            email = (session.get("customer_details") or {}).get("email") \
                or session.get("customer_email")
            product = get_product(product_id) if product_id else None
            if product and email:
                token = make_download_token(product_id)
                link = f"{SITE_URL}/api/download?token={token}"
                _email_download_link(email, product, link)

        # Always 200 so Stripe doesn't retry endlessly.
        return self._respond(200, {"received": True})
