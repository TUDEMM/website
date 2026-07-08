"""Vercel Serverless Function: create a Stripe Checkout Session.

The browser POSTs only { "product_id": "..." }. The server looks up the real
price from data/products.json, so the amount charged can never be tampered with
client-side. Returns the hosted Stripe Checkout URL to redirect the buyer to.

Env vars (Vercel → Settings → Environment Variables):
  STRIPE_SECRET_KEY   Your Stripe secret key (sk_live_... or sk_test_...).
  SITE_URL            e.g. https://tudemm.com (used for success/cancel redirects).
"""
import json
import os
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib.store import get_product, load_catalog  # noqa: E402

import stripe  # noqa: E402

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")
SITE_URL = os.environ.get("SITE_URL", "https://tudemm.com").rstrip("/")


class handler(BaseHTTPRequestHandler):
    def _respond(self, status, obj):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(json.dumps(obj).encode("utf-8"))

    def do_OPTIONS(self):
        self._respond(204, {})

    def do_POST(self):
        if not stripe.api_key:
            return self._respond(500, {"error": "Payments are not configured yet."})
        try:
            length = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(length) or b"{}")
        except Exception:
            return self._respond(400, {"error": "Invalid request."})

        product_id = (data.get("product_id") or "").strip()
        product = get_product(product_id)
        if not product:
            return self._respond(404, {"error": "Product not found."})

        currency = load_catalog().get("currency", "usd")
        try:
            session = stripe.checkout.Session.create(
                mode="payment",
                line_items=[{
                    "price_data": {
                        "currency": currency,
                        "unit_amount": product["price_cents"],  # trusted, server-side
                        "product_data": {
                            "name": product["name"],
                            "description": product.get("category", ""),
                        },
                    },
                    "quantity": 1,
                }],
                metadata={"product_id": product_id},
                # Collect the buyer's email so we can deliver the file.
                customer_creation="always",
                success_url=f"{SITE_URL}/pages/success.html?session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=f"{SITE_URL}/pages/products.html",
            )
            return self._respond(200, {"url": session.url})
        except Exception as e:  # noqa: BLE001
            return self._respond(502, {"error": f"Could not start checkout: {e}"})
