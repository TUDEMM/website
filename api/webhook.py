"""Vercel Serverless Function: Stripe webhook — fulfillment + email delivery.

Stripe calls this URL after a payment. We verify the signature (so nobody can
fake a "paid" event), then email the buyer a secure, expiring download link for
the e-book they purchased. Delivery uses the shared deliver_download_email()
helper, so Stripe and PayPal fulfill orders identically.

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
from http.server import BaseHTTPRequestHandler
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib.store import get_product, deliver_download_email  # noqa: E402

import stripe  # noqa: E402

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")
WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")


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
                deliver_download_email(email, product)

        # Always 200 so Stripe doesn't retry endlessly.
        return self._respond(200, {"received": True})
