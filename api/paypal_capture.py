"""Vercel Serverless Function: capture a PayPal order + deliver the e-book.

After the buyer approves payment in the PayPal popup, the front-end sends the
order id here. The server captures the payment DIRECTLY with PayPal (so the
"paid" status is confirmed server-side and cannot be faked by the browser),
re-checks that the captured amount matches the catalog price (anti-tamper),
then emails the buyer the same secure, expiring download link that Stripe uses.

Env vars:
  PAYPAL_CLIENT_ID, PAYPAL_CLIENT_SECRET, PAYPAL_ENV   (see paypal_create.py)
  DOWNLOAD_SECRET, RESEND_API_KEY, CONTACT_FROM, SITE_URL  (shared with Stripe)
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
from _lib.store import get_product, load_catalog, deliver_download_email  # noqa: E402

PAYPAL_CLIENT_ID = os.environ.get("PAYPAL_CLIENT_ID", "")
PAYPAL_CLIENT_SECRET = os.environ.get("PAYPAL_CLIENT_SECRET", "")
PAYPAL_ENV = os.environ.get("PAYPAL_ENV", "sandbox").strip().lower()
PAYPAL_API = "https://api-m.paypal.com" if PAYPAL_ENV == "live" \
    else "https://api-m.sandbox.paypal.com"


def _paypal_access_token():
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

        order_id = (data.get("order_id") or "").strip()
        if not order_id:
            return self._respond(400, {"error": "Missing order id."})

        try:
            token = _paypal_access_token()
            # Capture the order server-side — this is the authoritative "paid" check.
            req = urllib.request.Request(
                f"{PAYPAL_API}/v2/checkout/orders/{order_id}/capture",
                data=b"{}",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                result = json.loads(resp.read())
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="ignore")[:300]
            return self._respond(502, {"error": f"PayPal capture failed: {detail}"})
        except Exception as e:  # noqa: BLE001
            return self._respond(502, {"error": f"Could not capture payment: {e}"})

        if result.get("status") != "COMPLETED":
            return self._respond(402, {"error": "Payment was not completed."})

        # Pull the product id and paid amount straight from PayPal's response.
        try:
            unit = result["purchase_units"][0]
            product_id = unit.get("custom_id") or unit.get("reference_id")
            cap = unit["payments"]["captures"][0]
            paid_value = cap["amount"]["value"]
            paid_currency = cap["amount"]["currency_code"].upper()
        except Exception:
            return self._respond(502, {"error": "Unexpected PayPal response."})

        product = get_product(product_id)
        if not product:
            return self._respond(404, {"error": "Product not found."})

        # Anti-tamper: confirm the captured amount matches the catalog price.
        expected_value = f"{product['price_cents'] / 100:.2f}"
        expected_currency = load_catalog().get("currency", "usd").upper()
        if paid_value != expected_value or paid_currency != expected_currency:
            return self._respond(400, {"error": "Payment amount mismatch."})

        # Buyer email from PayPal, then deliver the secure download link.
        email = ((result.get("payer") or {}).get("email_address")) or ""
        delivered = deliver_download_email(email, product) if email else False

        return self._respond(200, {"status": "COMPLETED", "delivered": delivered})
