"""Vercel Serverless Function: public product catalog for the storefront.

Returns the product list WITHOUT sensitive fields (file_key stays server-side).
The products page calls this to render the grid, so adding a product is just an
edit to data/products.json — no HTML changes needed.
"""
import json
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib.store import load_catalog  # noqa: E402


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        catalog = load_catalog()
        public = []
        for p in catalog.get("products", []):
            public.append({
                "id": p["id"],
                "name": p["name"],
                "category": p.get("category", ""),
                "description": p.get("description", ""),
                "price_cents": p["price_cents"],
                "compare_at_cents": p.get("compare_at_cents"),
                "cover": p.get("cover", ""),
                "badge": p.get("badge"),
            })
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "public, max-age=300")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps({"currency": catalog.get("currency", "usd"),
                                     "products": public}).encode("utf-8"))
