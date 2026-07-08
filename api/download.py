"""Vercel Serverless Function: secure, expiring e-book download.

Validates the HMAC-signed token from the purchase email. If valid and not
expired, it redirects to the actual file in private storage. Tokens cannot be
forged (HMAC) or reused forever (they expire), so paid files stay protected.

Env vars:
  DOWNLOAD_SECRET   same secret used to sign tokens in the webhook
  FILES_BASE_URL    base URL of your private file storage, e.g.
                    https://<bucket>.s3.amazonaws.com/ebooks  or a Vercel Blob URL.
                    The function appends the product's file_key.
"""
import os
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib.store import verify_download_token, get_product  # noqa: E402

FILES_BASE_URL = os.environ.get("FILES_BASE_URL", "").rstrip("/")


class handler(BaseHTTPRequestHandler):
    def _text(self, status, msg):
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(msg.encode("utf-8"))

    def do_GET(self):
        qs = parse_qs(urlparse(self.path).query)
        token = (qs.get("token") or [""])[0]

        product_id = verify_download_token(token)
        if not product_id:
            return self._text(403, "This download link is invalid or has expired. "
                                   "Please reply to your purchase email for a fresh link.")

        product = get_product(product_id)
        if not product:
            return self._text(404, "Product not found.")

        if not FILES_BASE_URL:
            return self._text(500, "File storage is not configured (missing FILES_BASE_URL).")

        # Redirect to the real file in private storage.
        file_url = f"{FILES_BASE_URL}/{product['file_key']}"
        self.send_response(302)
        self.send_header("Location", file_url)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
