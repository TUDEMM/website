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

    def do_GET(self):
        # Stripe only ever POSTs here. Without this, a browser visit falls through
        # to the runtime's default handler and leaks a Python error page.
        return self._respond(405, {"error": "Method not allowed. This endpoint accepts POST from Stripe only."})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        payload = self.rfile.read(length)
        sig = self.headers.get("Stripe-Signature", "")

        # Verify the event really came from Stripe.
        try:
            event = stripe.Webhook.construct_event(payload, sig, WEBHOOK_SECRET)
        except Exception:
            return self._respond(400, {"error": "Invalid signature."})

        if event["type"] != "checkout.session.completed":
            return self._respond(200, {"received": True, "ignored": event["type"]})

        try:
            # stripe-python >= 14 removed dict methods from StripeObject, so
            # session.get(...) raises AttributeError. Normalise to a real dict
            # first and this works on every library version.
            session = event["data"]["object"]
            data = session.to_dict() if hasattr(session, "to_dict") else dict(session)

            product_id = (data.get("metadata") or {}).get("product_id")
            email = (data.get("customer_details") or {}).get("email") \
                or data.get("customer_email")

            if not product_id:
                # Nothing to fulfil and retrying will not help — accept and move on.
                return self._respond(200, {"received": True, "note": "no product_id in metadata"})

            product = get_product(product_id)
            if not product:
                return self._respond(200, {"received": True, "note": f"unknown product {product_id}"})
            if not email:
                return self._respond(200, {"received": True, "note": "no buyer email on session"})

            if not deliver_download_email(email, product):
                # A paid order that was NOT delivered must fail loudly: a 500 makes
                # Stripe retry with backoff and shows red in Event deliveries,
                # instead of silently losing the sale behind a 200.
                return self._respond(500, {"error": "Delivery email failed to send.",
                                           "product_id": product_id})

            return self._respond(200, {"received": True, "delivered": product_id})

        except Exception as e:  # noqa: BLE001
            # Same reasoning: surface the failure so it is retried and visible.
            return self._respond(500, {"error": f"Fulfilment failed: {type(e).__name__}: {e}"})
