#!/usr/bin/env python3
"""api_server.py — TUDEMM contact form backend (port 8000).

Every contact submission is persisted to SQLite (data.db) the moment it
arrives, so no inquiry is ever lost. An admin endpoint exposes the saved
submissions so they can be reviewed (and later forwarded to info@tudemm.com
once the site lives on its production domain).
"""
import re
import sqlite3
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator

DB_PATH = "data.db"

db = sqlite3.connect(DB_PATH, check_same_thread=False)
db.row_factory = sqlite3.Row
db.execute(
    """
    CREATE TABLE IF NOT EXISTS submissions (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        name        TEXT    NOT NULL,
        email       TEXT    NOT NULL,
        company     TEXT,
        service     TEXT,
        message     TEXT    NOT NULL,
        visitor_id  TEXT,
        created_at  TEXT    NOT NULL
    )
    """
)
db.commit()

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@asynccontextmanager
async def lifespan(app):
    yield
    db.close()


app = FastAPI(title="TUDEMM Contact API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class Submission(BaseModel):
    name: str
    email: str
    company: str | None = ""
    service: str | None = ""
    message: str

    @field_validator("name", "message")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("This field is required.")
        return v.strip()

    @field_validator("email")
    @classmethod
    def valid_email(cls, v: str) -> str:
        v = (v or "").strip()
        if not EMAIL_RE.match(v):
            raise ValueError("Please enter a valid email address.")
        return v


@app.get("/api/health")
def health():
    return {"ok": True}


@app.post("/api/contact", status_code=201)
def create_submission(sub: Submission, x_visitor_id: str | None = Header(default=None)):
    try:
        created = datetime.now(timezone.utc).isoformat()
        cur = db.execute(
            """
            INSERT INTO submissions (name, email, company, service, message, visitor_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [sub.name, sub.email, sub.company or "", sub.service or "",
             sub.message, x_visitor_id or "", created],
        )
        db.commit()
    except Exception:
        raise HTTPException(status_code=422, detail="We couldn't save your message. Please try again.")

    return {
        "ok": True,
        "id": cur.lastrowid,
        "message": "Thanks — your message has been received and saved.",
    }


@app.get("/api/submissions")
def list_submissions():
    """Admin view of saved submissions (newest first)."""
    rows = db.execute(
        "SELECT id, name, email, company, service, message, created_at "
        "FROM submissions ORDER BY id DESC"
    ).fetchall()
    return {"count": len(rows), "submissions": [dict(r) for r in rows]}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
