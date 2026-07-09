"""Vercel Serverless Function: create a PayPal order.

The browser POSTs only { "product_id": "..." }. The server looks up the real
price from data/products.json (never trusting the client), authenticates to
PayPal with the account credentials, and creates an order. Returns the PayPal
order id, which the front-end PayPal button uses to render the approval flow.

Security: same model as Stripe — the amount comes from the server-side catalog,
so the price cannot be tampered with in the browser.

Env vars (Vercel → Settings → Environment Variables):
  PAYPAL_CLIENT_ID       Your PayPal REST app client id.
  PAYPAL_CLIENT_SECRET   Your PayPal REST app secret.
  PAYPAL_ENV             "sandbox" (testing) or "live" (real money). Default sandbox.
"""
import base64
import json
import os
import sys
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib.store import get_product, load_catalog  # noqa: E402

PAYPAL_CLIENT_ID = os.environ.get("PAYPAL_CLIENT_ID", "")
PAYPAL_CLIENT_SECRET = os.environ.get("PAYPAL_CLIENT_SECRET", "")
PAYPAL_ENV = os.environ.get("PAYPAL_ENV", "sandbox").strip().lower()
PAYPAL_API = "https://api-m.paypal.com" if PAYPAL_ENV == "live" \
    else "https://api-m.sandbox.paypal.com"


def _paypal_access_token():
    """Exchange client id/secret for a short-lived OAuth access token."""
    creds = f"{PAYPAL_CLIENT_ID}:{PAYPAL_CLIENT_SECRET}".encode()
    auth = base64.b64encode(creds).decode()
    req = urllib.request.Request(
        f"{PAYPAL_API}/v1/oauth2/token",
        data=b"grant_type=client_credentials",
        headers={
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read()).get("access_token")


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
        if not (PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET):
            return self._respond(500, {"error": "PayPal is not configured yet."})
        try:
            length = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(length) or b"{}")
        except Exception:
            return self._respond(400, {"error": "Invalid request."})

        product_id = (data.get("product_id") or "").strip()
        product = get_product(product_id)
        if not product:
            return self._respond(404, {"error": "Product not found."})

        currency = load_catalog().get("currency", "usd").upper()
        # PayPal wants a decimal string, e.g. "19.00". price_cents is trusted.
        amount = f"{product['price_cents'] / 100:.2f}"

        try:
            token = _paypal_access_token()
            order_body = {
                "intent": "CAPTURE",
                "purchase_units": [{
                    "reference_id": product_id,
                    "description": product["name"][:127],
                    "custom_id": product_id,
                    "amount": {"currency_code": currency, "value": amount},
                }],
                "application_context": {
                    "brand_name": "TUDEMM LLC",
                    "shipping_preference": "NO_SHIPPING",
                    "user_action": "PAY_NOW",
                },
            }
            req = urllib.request.Request(
                f"{PAYPAL_API}/v2/checkout/orders",
                data=json.dumps(order_body).encode(),
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                order = json.loads(resp.read())
            return self._respond(200, {"id": order.get("id")})
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="ignore")[:300]
            return self._respond(502, {"error": f"PayPal order failed: {detail}"})
        except Exception as e:  # noqa: BLE001
            return self._respond(502, {"error": f"Could not start PayPal checkout: {e}"})
