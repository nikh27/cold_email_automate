"""
config.py — Central configuration loaded from environment variables.
On Render: set these in the Environment tab of your service.
Locally: copy .env.example to .env and fill in your details.
"""
import os
from dotenv import load_dotenv

# Use the folder this file lives in — works regardless of launch directory
_HERE = os.path.dirname(os.path.abspath(__file__))
load_dotenv(dotenv_path=os.path.join(_HERE, ".env"), override=True)

# ── Gmail ──────────────────────────────────────────────────────────────────
GMAIL_USER          = os.environ.get("GMAIL_USER", "")
GMAIL_APP_PASSWORD  = os.environ.get("GMAIL_APP_PASSWORD", "")

# ── Sender identity (shown in From: field) ─────────────────────────────────
SENDER_NAME         = "Soumya Kumari"

# ── Sending pace ───────────────────────────────────────────────────────────
DAILY_LIMIT         = int(os.environ.get("DAILY_LIMIT", 62))
MORNING_BATCH_SIZE  = int(os.environ.get("MORNING_BATCH_SIZE", 30))
EVENING_BATCH_SIZE  = int(os.environ.get("EVENING_BATCH_SIZE", 32))

# Random delay between each email (seconds) — keeps it human
MIN_DELAY_SECONDS   = int(os.environ.get("MIN_DELAY", 90))
MAX_DELAY_SECONDS   = int(os.environ.get("MAX_DELAY", 240))

# ── File paths ─────────────────────────────────────────────────────────────
CONTACTS_FILE       = os.environ.get("CONTACTS_FILE", "Company Wise HR Contacts - HR Contacts.xlsx")
DB_FILE             = os.environ.get("DB_FILE", "email_tracker.db")
RESUME_FILE         = os.environ.get("RESUME_FILE", "resume.pdf")
RESUME_DRIVE_ID     = "1YYsVNprr4NMfnXRl68Iq3tQ8DyO2VvON"

# ── Security ───────────────────────────────────────────────────────────────
SECRET_KEY          = os.environ.get("SECRET_KEY", "cold-email-soumya-2026")
API_KEY             = os.environ.get("API_KEY", "")   # Protects /api/send-batch
