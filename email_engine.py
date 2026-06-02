"""
email_engine.py — Core sending logic.

Key behaviours:
  1. Downloads resume from Google Drive if resume.pdf is missing.
  2. Sends one email via Gmail SMTP with TLS.
  3. Attaches resume.pdf to every email.
  4. send_batch() respects daily limits and random human delays.
  5. send_batch() runs safely in a background thread (non-blocking for Flask).
"""

import os
import time
import random
import logging
import smtplib
import threading
import requests
from email.mime.multipart import MIMEMultipart
from email.mime.text      import MIMEText
from email.mime.base      import MIMEBase
from email                import encoders

import config
import database as db
from email_templates import get_email_content

logger = logging.getLogger(__name__)

# Thread lock so only one batch runs at a time
_batch_lock = threading.Lock()
_is_running = False   # exposed to dashboard


# ── Resume Download ──────────────────────────────────────────────────────────

def download_resume() -> bool:
    """
    Download Soumya's resume PDF from Google Drive.
    Handles the 'virus scan warning' redirect that Google adds for large files.
    """
    if os.path.exists(config.RESUME_FILE) and os.path.getsize(config.RESUME_FILE) > 10_000:
        logger.info("📎 Resume already present.")
        return True

    logger.info("⬇️  Downloading resume from Google Drive …")
    drive_id = config.RESUME_DRIVE_ID
    session  = requests.Session()

    try:
        # First request — may return a scan warning page
        url      = f"https://drive.google.com/uc?export=download&id={drive_id}"
        response = session.get(url, stream=True, timeout=30)

        # Look for the confirm token Google embeds in the cookie / response
        confirm_token = None
        for key, value in response.cookies.items():
            if "download_warning" in key:
                confirm_token = value
                break

        if confirm_token:
            response = session.get(
                "https://drive.google.com/uc",
                params={"id": drive_id, "confirm": confirm_token, "export": "download"},
                stream=True,
                timeout=30,
            )

        if response.status_code == 200:
            with open(config.RESUME_FILE, "wb") as f:
                for chunk in response.iter_content(chunk_size=32_768):
                    if chunk:
                        f.write(chunk)
            size_kb = os.path.getsize(config.RESUME_FILE) // 1024
            logger.info(f"✅ Resume downloaded ({size_kb} KB) → {config.RESUME_FILE}")
            return True
        else:
            logger.error(f"❌ Drive returned HTTP {response.status_code}")
            return False

    except Exception as exc:
        logger.error(f"❌ Resume download failed: {exc}")
        return False


# ── Build MIME Message ───────────────────────────────────────────────────────

def _build_message(to_email: str, subject: str, body: str) -> MIMEMultipart:
    msg = MIMEMultipart()
    msg["From"]    = f"{config.SENDER_NAME} <{config.GMAIL_USER}>"
    msg["To"]      = to_email
    msg["Subject"] = subject

    msg.attach(MIMEText(body, "plain", "utf-8"))

    if os.path.exists(config.RESUME_FILE):
        with open(config.RESUME_FILE, "rb") as f:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header(
            "Content-Disposition",
            'attachment; filename="Soumya_Kumari_Resume.pdf"',
        )
        msg.attach(part)

    return msg


# ── Send One Email ───────────────────────────────────────────────────────────

def send_single_email(contact: dict) -> tuple:
    """
    Attempt to send email to one contact.
    Returns (success: bool, error_msg: str | None, template_index: int)
    """
    content        = get_email_content(contact)
    subject        = content["subject"]
    body           = content["body"]
    template_index = content["template_index"]

    try:
        msg = _build_message(contact["email"], subject, body)

        with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(config.GMAIL_USER, config.GMAIL_APP_PASSWORD)
            server.send_message(msg)

        logger.info(
            f"✅ Sent → {contact['email']} | {contact.get('company','')} | Template {template_index}"
        )
        return True, None, template_index

    except smtplib.SMTPRecipientsRefused:
        return False, "Invalid email address (refused by server)", template_index
    except smtplib.SMTPAuthenticationError:
        return False, "Gmail authentication failed — check App Password in env", template_index
    except smtplib.SMTPException as exc:
        return False, f"SMTP error: {exc}", template_index
    except Exception as exc:
        return False, f"Unexpected error: {exc}", template_index


# ── Batch Sender ─────────────────────────────────────────────────────────────

def send_batch(batch_size: int = None) -> dict:
    """
    Send the next N pending emails with human-like delays.
    Thread-safe: only one batch runs at a time.
    Returns a result dict suitable for JSON responses.
    """
    global _is_running

    if not _batch_lock.acquire(blocking=False):
        logger.warning("⚠️  Batch already running — skipping duplicate trigger.")
        return {"status": "already_running", "sent": 0, "failed": 0}

    _is_running = True
    try:
        return _do_send_batch(batch_size)
    finally:
        _is_running = False
        _batch_lock.release()


def _do_send_batch(batch_size: int) -> dict:
    """Internal batch execution (runs under lock)."""
    if db.is_paused():
        logger.info("⏸️  Sending paused — skipping batch.")
        return {"status": "paused", "sent": 0, "failed": 0}

    if not config.GMAIL_USER or not config.GMAIL_APP_PASSWORD:
        logger.error("❌ GMAIL_USER or GMAIL_APP_PASSWORD not set in environment.")
        return {"status": "config_error", "sent": 0, "failed": 0}

    if batch_size is None:
        batch_size = config.MORNING_BATCH_SIZE

    # Check today's remaining quota
    today_sent      = db.get_today_sent_count()
    remaining_today = config.DAILY_LIMIT - today_sent

    if remaining_today <= 0:
        logger.info(f"📊 Daily limit reached ({config.DAILY_LIMIT}). Done for today.")
        return {"status": "daily_limit_reached", "sent": 0, "failed": 0}

    actual_size = min(batch_size, remaining_today)
    contacts    = db.get_pending_contacts(limit=actual_size)

    if not contacts:
        logger.info("✨ All contacts emailed! No pending contacts left.")
        return {"status": "no_pending", "sent": 0, "failed": 0}

    logger.info(f"📧 Starting batch: {len(contacts)} emails (daily quota left: {remaining_today})")

    sent_count   = 0
    failed_count = 0

    for i, contact in enumerate(contacts):
        success, error, template_idx = send_single_email(contact)

        if success:
            db.mark_sent(contact["id"], template_idx)
            sent_count += 1
        else:
            db.mark_failed(contact["id"], error)
            failed_count += 1
            logger.warning(f"❌ Failed {contact['email']}: {error}")

        # Human delay between emails (skip after last one)
        if i < len(contacts) - 1:
            delay = random.randint(config.MIN_DELAY_SECONDS, config.MAX_DELAY_SECONDS)
            logger.info(f"💤 Waiting {delay}s before next send …")
            time.sleep(delay)

    result = {
        "status":      "done",
        "sent":        sent_count,
        "failed":      failed_count,
        "total_today": today_sent + sent_count,
    }
    logger.info(f"🎯 Batch finished: {result}")
    return result


def send_batch_async(batch_size: int = None):
    """Launch send_batch in a background thread. Returns immediately."""
    t = threading.Thread(target=send_batch, args=(batch_size,), daemon=True)
    t.start()
    logger.info("🔄 Batch dispatched to background thread.")
