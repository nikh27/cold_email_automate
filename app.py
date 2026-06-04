"""
app.py — Flask web application + APScheduler background jobs.

Endpoints:
  GET  /                         → Dashboard (HTML)
  GET  /health                   → Keep-alive ping (JSON)
  GET  /api/stats                → Aggregate stats (JSON)
  GET  /api/contacts             → Paginated contacts (?page&limit&status&search)
  GET  /api/daily-stats          → Daily send counts for chart (?days=14)
  GET  /api/template-stats       → Template usage counts
  GET  /api/recent               → Recent 50 sent/failed
  GET  /api/logs                 → Last 200 live log lines (JSON)
  POST /api/send-batch           → Trigger batch (?type=morning|evening)
  POST /api/toggle-pause         → Pause / resume
  POST /api/test                 → Send test email to a custom address
  POST /api/send-one             → Manually send to one contact by ID
  POST /api/settings             → Update daily limit / delays
  GET  /api/settings             → Get current settings
"""

import os
import logging
import collections
from datetime import datetime

import pytz
from flask import Flask, render_template, jsonify, request, redirect, url_for
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

import config
import database as db
import email_engine as engine
from email_templates import TEMPLATES as EMAIL_TEMPLATES, SUBJECTS as EMAIL_SUBJECTS

# ── In-memory log buffer (last 200 lines) ────────────────────────────────────

LOG_BUFFER = collections.deque(maxlen=200)

class DequeHandler(logging.Handler):
    def emit(self, record):
        LOG_BUFFER.append({
            "time":  datetime.now(pytz.timezone("Asia/Kolkata")).strftime("%H:%M:%S"),
            "level": record.levelname,
            "msg":   self.format(record),
        })

_deque_handler = DequeHandler()
_deque_handler.setFormatter(logging.Formatter("%(name)s: %(message)s"))

# ── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
root_logger = logging.getLogger()
root_logger.addHandler(_deque_handler)
logger = logging.getLogger(__name__)

# ── App ───────────────────────────────────────────────────────────────────────

app = Flask(__name__)
app.secret_key = config.SECRET_KEY
IST = pytz.timezone("Asia/Kolkata")


# ── Startup ───────────────────────────────────────────────────────────────────

def startup():
    logger.info("🚀 Cold Email System — Starting up …")
    db.initialize_db()
    engine.download_resume()
    stats = db.get_stats()
    logger.info(
        f"📊 Status: {stats['sent']} sent | {stats['pending']} pending | "
        f"{stats['failed']} failed | {stats['progress']}% complete"
    )
    logger.info(f"📮 SMTP relay: {config.SMTP_HOST}:{config.SMTP_PORT} → From: {config.SENDER_EMAIL}")


# ── Scheduler ─────────────────────────────────────────────────────────────────

scheduler = BackgroundScheduler(timezone=IST)
scheduler.add_job(
    lambda: engine.send_batch_async(config.MORNING_BATCH_SIZE),
    CronTrigger(hour=10, minute=0, timezone=IST),
    id="morning_batch", replace_existing=True,
)
scheduler.add_job(
    lambda: engine.send_batch_async(config.EVENING_BATCH_SIZE),
    CronTrigger(hour=15, minute=0, timezone=IST),
    id="evening_batch", replace_existing=True,
)


# ── Auth helper ───────────────────────────────────────────────────────────────

def _verify_api_key() -> bool:
    if not config.API_KEY:
        return True
    provided = request.headers.get("X-API-Key") or request.args.get("key", "")
    return provided == config.API_KEY


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def dashboard():
    return render_template("dashboard.html")


@app.route("/health")
def health():
    stats = db.get_stats()
    return jsonify({
        "status":    "alive",
        "timestamp": datetime.now(IST).isoformat(),
        "sent":      stats["sent"],
        "pending":   stats["pending"],
        "progress":  stats["progress"],
        "paused":    db.is_paused(),
        "running":   engine._is_running,
    })


@app.route("/api/debug-config")
def debug_config():
    pwd = config.SMTP_PASSWORD
    return jsonify({
        "sender_email":    config.SENDER_EMAIL,
        "smtp_host":       config.SMTP_HOST,
        "smtp_port":       config.SMTP_PORT,
        "smtp_user":       config.SMTP_USER,
        "password_set":    len(pwd) > 5,
        "password_preview": pwd[:4] + "…" if pwd else "EMPTY",
        "daily_limit":     config.DAILY_LIMIT,
    })


@app.route("/api/stats")
def api_stats():
    stats = db.get_stats()
    stats["paused"]  = db.is_paused()
    stats["running"] = engine._is_running
    stats["now_ist"] = datetime.now(IST).strftime("%d %b %Y, %I:%M %p")
    return jsonify(stats)


@app.route("/api/contacts")
def api_contacts():
    page   = int(request.args.get("page", 1))
    limit  = int(request.args.get("limit", 50))
    status = request.args.get("status", "all")
    search = request.args.get("search", "").strip()
    return jsonify(db.get_contacts_paginated(page, limit, status, search))


@app.route("/api/daily-stats")
def api_daily_stats():
    days = int(request.args.get("days", 14))
    return jsonify(db.get_daily_stats(days))


@app.route("/api/template-stats")
def api_template_stats():
    raw   = db.get_template_stats()
    names = ["Direct & Confident", "Value Focused", "Story-Based",
             "Short & Punchy", "Confident Fresher"]
    result = []
    counts = {r["template_used"]: r["count"] for r in raw}
    for i, name in enumerate(names):
        result.append({"index": i, "name": name, "count": counts.get(i, 0)})
    return jsonify(result)


@app.route("/api/recent")
def api_recent():
    limit = int(request.args.get("limit", 50))
    return jsonify(db.get_recent_emails(limit))


@app.route("/api/logs")
def api_logs():
    return jsonify(list(LOG_BUFFER))


@app.route("/api/settings", methods=["GET"])
def api_settings_get():
    return jsonify({
        "daily_limit":        config.DAILY_LIMIT,
        "morning_batch_size": config.MORNING_BATCH_SIZE,
        "evening_batch_size": config.EVENING_BATCH_SIZE,
        "min_delay":          config.MIN_DELAY_SECONDS,
        "max_delay":          config.MAX_DELAY_SECONDS,
        "sender_email":       config.SENDER_EMAIL,
        "smtp_host":          config.SMTP_HOST,
        "resume_present":     os.path.exists(config.RESUME_FILE),
        "resume_size_kb":     (os.path.getsize(config.RESUME_FILE) // 1024
                               if os.path.exists(config.RESUME_FILE) else 0),
    })


@app.route("/api/settings", methods=["POST"])
def api_settings_post():
    data = request.json or {}
    changed = []
    if "daily_limit" in data:
        val = int(data["daily_limit"])
        if 10 <= val <= 200:
            config.DAILY_LIMIT = val
            changed.append(f"daily_limit={val}")
    if "min_delay" in data:
        val = int(data["min_delay"])
        if 30 <= val <= 600:
            config.MIN_DELAY_SECONDS = val
            changed.append(f"min_delay={val}")
    if "max_delay" in data:
        val = int(data["max_delay"])
        if 60 <= val <= 900:
            config.MAX_DELAY_SECONDS = val
            changed.append(f"max_delay={val}")
    if changed:
        logger.info(f"⚙️ Settings updated: {', '.join(changed)}")
        return jsonify({"status": "ok", "changed": changed})
    return jsonify({"status": "no_change"})


@app.route("/api/send-batch", methods=["GET", "POST"])
def api_send_batch():
    if not _verify_api_key():
        return jsonify({"error": "Unauthorized"}), 401
    batch_type = request.args.get("type", "morning")
    size = config.EVENING_BATCH_SIZE if batch_type == "evening" else config.MORNING_BATCH_SIZE
    engine.send_batch_async(size)
    return jsonify({"status": "started", "type": batch_type, "size": size})


@app.route("/api/toggle-pause", methods=["POST"])
def toggle_pause():
    paused = db.is_paused()
    db.set_paused(not paused)
    action = "resumed" if paused else "paused"
    logger.info(f"📌 Sending {action}.")
    if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.is_json:
        return jsonify({"paused": not paused})
    return redirect(url_for("dashboard"))


@app.route("/api/test", methods=["POST"])
def api_test():
    """Send 1 test email to a user-specified address."""
    data       = request.get_json(force=True, silent=True) or {}
    test_email = data.get("email", "").strip() or config.SENDER_EMAIL

    if not config.SMTP_USER or not config.SMTP_PASSWORD:
        return jsonify({"error": "SMTP credentials not configured"}), 400

    if not test_email:
        return jsonify({"error": "No email address provided"}), 400

    contact = {
        "id":      9001,
        "name":    "Test HR",
        "email":   test_email,
        "title":   "Head of HR",
        "company": "TestCorp",
    }
    ok, err, tmpl = engine.send_single_email(contact)
    return jsonify({
        "status":   "done",
        "success":  ok,
        "to":       test_email,
        "template": tmpl,
        "error":    err,
    })


@app.route("/api/send-one", methods=["POST"])
def api_send_one():
    """
    Manually send email to one contact by ID.
    Only allowed if contact status is 'pending' or 'failed'.
    Skips contacts that are already 'sent'.
    """
    data       = request.get_json(force=True, silent=True) or {}
    contact_id = data.get("id")

    if not contact_id:
        return jsonify({"error": "Missing contact id"}), 400

    # Fetch contact from DB
    contact = db.get_contact_by_id(int(contact_id))
    if not contact:
        return jsonify({"error": "Contact not found"}), 404

    # Block re-sending to already sent contacts
    if contact.get("status") == "sent":
        return jsonify({
            "error":   "Already sent to this contact",
            "skipped": True,
            "status":  "sent",
        }), 400

    logger.info(f"📤 Manual send → {contact['email']} ({contact.get('company','')})")
    ok, err, tmpl = engine.send_single_email(contact)

    if ok:
        db.mark_sent(contact["id"], tmpl)
        logger.info(f"✅ Manual send success → {contact['email']}")
        return jsonify({"success": True, "email": contact["email"], "template": tmpl})
    else:
        db.mark_failed(contact["id"], err)
        logger.warning(f"❌ Manual send failed → {contact['email']}: {err}")
        return jsonify({"success": False, "email": contact["email"], "error": err})


@app.route("/api/templates")
def api_templates():
    names = ["Direct & Confident", "Value Focused", "Story-Based",
             "Short & Punchy", "Confident Fresher"]
    templates = []
    for i, (name, body) in enumerate(zip(names, EMAIL_TEMPLATES)):
        templates.append({
            "index":   i,
            "name":    name,
            "body":    body.format(first_name="[HR Name]", company="[Company]"),
            "subject": EMAIL_SUBJECTS[i % len(EMAIL_SUBJECTS)],
        })
    return jsonify({"templates": templates, "subjects": EMAIL_SUBJECTS})


# ── Entry point ───────────────────────────────────────────────────────────────

startup()
scheduler.start()
logger.info("⏰ Scheduler started (10:00 AM and 3:00 PM IST daily)")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
