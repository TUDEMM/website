"""Vercel Serverless Function: TUDEMM contact form handler.

Receives a POST from the website contact form, validates it, and emails the
submission to info.tudemm@gmail.com via Resend (https://resend.com).

Environment variables (set these in Vercel → Project → Settings → Environment Variables):
  RESEND_API_KEY   Your Resend API key (starts with "re_").
  CONTACT_TO       Destination inbox. Defaults to info.tudemm@gmail.com.
  CONTACT_FROM     Verified sender. Until you verify tudemm.com in Resend,
                   use "onboarding@resend.dev" (Resend's shared test sender).

Vercel automatically exposes this file at the path /api/contact.
"""
import json
import os
import re
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

TO_ADDR = os.environ.get("CONTACT_TO", "info.tudemm@gmail.com")
FROM_ADDR = os.environ.get("CONTACT_FROM", "TUDEMM Website <onboarding@resend.dev>")
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")


def _send_email(payload):
    """Send the submission to the TUDEMM inbox via Resend. Returns (ok, error)."""
    if not RESEND_API_KEY:
        return False, "Email service is not configured (missing RESEND_API_KEY)."

    name = payload["name"]
    email = payload["email"]
    company = payload.get("company") or "—"
    service = payload.get("service") or "—"
    message = payload["message"]

    text_body = (
        f"New contact form submission from tudemm.com\n\n"
        f"Name:    {name}\n"
        f"Email:   {email}\n"
        f"Company: {company}\n"
        f"Service: {service}\n\n"
        f"Message:\n{message}\n"
    )
    html_body = (
        f"<h2>New contact form submission</h2>"
        f"<p><strong>Name:</strong> {name}</p>"
        f"<p><strong>Email:</strong> <a href='mailto:{email}'>{email}</a></p>"
        f"<p><strong>Company:</strong> {company}</p>"
        f"<p><strong>Service:</strong> {service}</p>"
        f"<p><strong>Message:</strong><br>{message}</p>"
    )

    body = {
        "from": FROM_ADDR,
        "to": [TO_ADDR],
        "reply_to": email,
        "subject": f"Website inquiry from {name}",
        "text": text_body,
        "html": html_body,
    }
    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if 200 <= resp.status < 300:
                return True, None
            return False, f"Email service returned status {resp.status}."
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "ignore")
        return False, f"Email service error: {detail}"
    except Exception as e:  # noqa: BLE001
        return False, f"Could not reach the email service: {e}"


class handler(BaseHTTPRequestHandler):
    def _respond(self, status, obj):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(json.dumps(obj).encode("utf-8"))

    def do_OPTIONS(self):  # CORS preflight
        self._respond(204, {})

    def do_GET(self):  # simple health check
        self._respond(200, {"ok": True, "service": "tudemm-contact"})

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length) if length else b"{}"
            data = json.loads(raw or b"{}")
        except Exception:
            return self._respond(400, {"ok": False, "detail": "Invalid request."})

        name = (data.get("name") or "").strip()
        email = (data.get("email") or "").strip()
        message = (data.get("message") or "").strip()
        company = (data.get("company") or "").strip()
        service = (data.get("service") or "").strip()

        if not name or not email or not message:
            return self._respond(
                422, {"ok": False, "detail": "Please fill in your name, email, and message."}
            )
        if not EMAIL_RE.match(email):
            return self._respond(
                422, {"ok": False, "detail": "Please enter a valid email address."}
            )

        payload = {
            "name": name, "email": email, "message": message,
            "company": company, "service": service,
        }
        ok, err = _send_email(payload)
        if not ok:
            return self._respond(
                502,
                {"ok": False, "detail": err or "We couldn't send your message. Please email info.tudemm@gmail.com."},
            )

        return self._respond(
            201, {"ok": True, "message": "Thanks — your message has been sent."}
        )
