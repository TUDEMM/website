"""Vercel Serverless Function: secure, expiring e-book download.

Validates the HMAC-signed token from the purchase email. If valid and not
expired, it fetches the file from private Vercel Blob storage (using the
store's read/write token for auth) and streams it back to the buyer. Tokens
cannot be forged (HMAC) or reused forever (they expire), so paid files stay
protected — and the underlying Blob store stays private, never directly
publicly reachable.

Env vars:
  DOWNLOAD_SECRET        same secret used to sign tokens in the webhook
  FILES_BASE_URL         base URL of the private Vercel Blob store, e.g.
                         https://<store-id>.private.blob.vercel-storage.com
                         The function appends the product's file_key.
  BLOB_READ_WRITE_TOKEN  auto-added when the Blob store is connected to this
                         project. Required to read from a private store.
"""
import os
import sys
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs, quote

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib.store import verify_download_token, get_product  # noqa: E402

FILES_BASE_URL = os.environ.get("FILES_BASE_URL", "").rstrip("/")
BLOB_READ_WRITE_TOKEN = os.environ.get("BLOB_READ_WRITE_TOKEN", "")


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

        if not FILES_BASE_URL or not BLOB_READ_WRITE_TOKEN:
            return self._text(500, "File storage is not configured (missing FILES_BASE_URL or "
                                    "BLOB_READ_WRITE_TOKEN).")

        # Fetch the file from private Blob storage server-side (a plain redirect
        # would 403 — private blobs require an authenticated request) and stream
        # the bytes back to the buyer.
        file_url = f"{FILES_BASE_URL}/{quote(product['file_key'])}"
        req = urllib.request.Request(
            file_url,
            headers={"Authorization": f"Bearer {BLOB_READ_WRITE_TOKEN}"},
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = resp.read()
        except urllib.error.HTTPError as e:
            return self._text(502, f"We couldn't retrieve your file right now (storage error "
                                    f"{e.code}). Please reply to your purchase email for help.")
        except Exception:
            return self._text(502, "We couldn't retrieve your file right now. Please reply to "
                                    "your purchase email for help.")

        filename = product["file_key"].rsplit("/", 1)[-1]
        self.send_response(200)
        self.send_header("Content-Type", "application/pdf")
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)
