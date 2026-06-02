"""
database.py — SQLite-backed contact tracker.

Schema:
  contacts      — every HR person, with their current email status
  system_config — key/value store (paused flag, etc.)

Fault tolerance:
  On every startup, initialize_db() is called.
  Contacts already marked 'sent' are never touched again.
  'failed' contacts get up to 3 retries before being skipped.
"""

import sqlite3
import logging
from datetime import date, datetime

import config

logger = logging.getLogger(__name__)


# ── Connection ──────────────────────────────────────────────────────────────

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(config.DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


# ── Initialization ──────────────────────────────────────────────────────────

def initialize_db():
    """Create tables and import contacts from Excel on first run."""
    conn = get_connection()
    c = conn.cursor()

    c.executescript("""
        CREATE TABLE IF NOT EXISTS contacts (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            sno           INTEGER,
            name          TEXT    NOT NULL,
            email         TEXT    NOT NULL UNIQUE,
            title         TEXT,
            company       TEXT,
            status        TEXT    DEFAULT 'pending',
            sent_at       TEXT,
            retry_count   INTEGER DEFAULT 0,
            error_msg     TEXT,
            template_used INTEGER,
            batch_date    TEXT
        );

        CREATE TABLE IF NOT EXISTS system_config (
            key   TEXT PRIMARY KEY,
            value TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_status ON contacts(status);
        CREATE INDEX IF NOT EXISTS idx_batch_date ON contacts(batch_date);
    """)
    conn.commit()

    # Import contacts only once (when table is empty)
    count = c.execute("SELECT COUNT(*) FROM contacts").fetchone()[0]
    if count == 0:
        _import_contacts_from_excel(conn, c)

    conn.close()
    logger.info("✅ Database initialized")


def _import_contacts_from_excel(conn, c):
    """Load all rows from Excel into contacts table."""
    try:
        import openpyxl
        wb = openpyxl.load_workbook(config.CONTACTS_FILE)
        ws = wb.active

        rows = list(ws.iter_rows(values_only=True))
        imported = 0

        for row in rows[1:]:  # Skip header row
            if len(row) < 3:
                continue
            sno, name, email, title, company = (list(row) + [None, None, None])[:5]

            if not email or "@" not in str(email):
                continue

            try:
                c.execute("""
                    INSERT OR IGNORE INTO contacts (sno, name, email, title, company)
                    VALUES (?, ?, ?, ?, ?)
                """, (sno, str(name).strip() if name else "Unknown",
                      str(email).strip().lower(), title, company))
                imported += 1
            except Exception as e:
                logger.warning(f"Skipped row (import error): {e}")

        conn.commit()
        logger.info(f"📋 Imported {imported} contacts from Excel")

    except FileNotFoundError:
        logger.error(f"❌ Contacts file not found: {config.CONTACTS_FILE}")
    except Exception as e:
        logger.error(f"❌ Import failed: {e}")


# ── Read Operations ─────────────────────────────────────────────────────────

def get_pending_contacts(limit: int = 30) -> list[dict]:
    """
    Return next batch of contacts to email.
    Priority: pending first, then failed (retry_count < 3), ordered by id ASC.
    """
    conn = get_connection()
    rows = conn.execute("""
        SELECT id, name, email, title, company, retry_count
        FROM contacts
        WHERE status = 'pending'
           OR (status = 'failed' AND retry_count < 3)
        ORDER BY
            CASE WHEN status = 'pending' THEN 0 ELSE 1 END,
            id ASC
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_stats() -> dict:
    """Return aggregate counts for the dashboard."""
    conn = get_connection()
    c = conn.cursor()
    today = date.today().isoformat()

    total   = c.execute("SELECT COUNT(*) FROM contacts").fetchone()[0]
    sent    = c.execute("SELECT COUNT(*) FROM contacts WHERE status = 'sent'").fetchone()[0]
    pending = c.execute("SELECT COUNT(*) FROM contacts WHERE status = 'pending'").fetchone()[0]
    failed  = c.execute("SELECT COUNT(*) FROM contacts WHERE status = 'failed'").fetchone()[0]
    today_s = c.execute("SELECT COUNT(*) FROM contacts WHERE status = 'sent' AND batch_date = ?",
                        (today,)).fetchone()[0]
    conn.close()

    progress     = round(sent / total * 100, 1) if total > 0 else 0.0
    days_left    = round(pending / config.DAILY_LIMIT) if config.DAILY_LIMIT > 0 else 0

    return {
        "total":       total,
        "sent":        sent,
        "pending":     pending,
        "failed":      failed,
        "today_sent":  today_s,
        "today_limit": config.DAILY_LIMIT,
        "progress":    progress,
        "days_left":   days_left,
    }


def get_recent_emails(limit: int = 50) -> list[dict]:
    """Return the most recently processed contacts for the dashboard table."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT name, email, company, title, status, sent_at, error_msg
        FROM contacts
        WHERE status IN ('sent', 'failed')
        ORDER BY sent_at DESC
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_contacts_paginated(page: int = 1, limit: int = 50,
                           status: str = 'all', search: str = '') -> dict:
    """Return a page of contacts with optional status filter and search."""
    conn = get_connection()
    offset = (page - 1) * limit

    conditions, params = [], []
    if status != 'all':
        conditions.append("status = ?")
        params.append(status)
    if search:
        conditions.append("(name LIKE ? OR email LIKE ? OR company LIKE ?)")
        term = f"%{search}%"
        params.extend([term, term, term])

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    total = conn.execute(
        f"SELECT COUNT(*) FROM contacts {where}", params
    ).fetchone()[0]

    rows = conn.execute(
        f"""
        SELECT id, sno, name, email, title, company,
               status, sent_at, retry_count, template_used, error_msg
        FROM contacts {where}
        ORDER BY id ASC
        LIMIT ? OFFSET ?
        """,
        params + [limit, offset]
    ).fetchall()
    conn.close()

    return {
        "total":    total,
        "page":     page,
        "limit":    limit,
        "pages":    max(1, (total + limit - 1) // limit),
        "contacts": [dict(r) for r in rows],
    }


def get_daily_stats(days: int = 14) -> list[dict]:
    """Return daily sent counts for the last N days (for bar chart)."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT batch_date as date, COUNT(*) as count
        FROM contacts
        WHERE status = 'sent' AND batch_date IS NOT NULL
        GROUP BY batch_date
        ORDER BY batch_date DESC
        LIMIT ?
    """, (days,)).fetchall()
    conn.close()
    return [dict(r) for r in reversed(rows)]


def get_template_stats() -> list[dict]:
    """Return how many times each template was used."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT template_used, COUNT(*) as count
        FROM contacts
        WHERE status = 'sent' AND template_used IS NOT NULL
        GROUP BY template_used
        ORDER BY template_used
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_today_sent_count() -> int:
    conn = get_connection()
    count = conn.execute(
        "SELECT COUNT(*) FROM contacts WHERE status='sent' AND batch_date=?",
        (date.today().isoformat(),)
    ).fetchone()[0]
    conn.close()
    return count


# ── Write Operations ────────────────────────────────────────────────────────

def mark_sent(contact_id: int, template_used: int):
    conn = get_connection()
    conn.execute("""
        UPDATE contacts
        SET status='sent', sent_at=?, template_used=?, batch_date=?, error_msg=NULL
        WHERE id=?
    """, (datetime.now().isoformat(), template_used, date.today().isoformat(), contact_id))
    conn.commit()
    conn.close()


def mark_failed(contact_id: int, error_msg: str):
    conn = get_connection()
    conn.execute("""
        UPDATE contacts
        SET status='failed', retry_count=retry_count+1, error_msg=?, batch_date=?
        WHERE id=?
    """, (str(error_msg)[:500], date.today().isoformat(), contact_id))
    conn.commit()
    conn.close()


# ── System Config ────────────────────────────────────────────────────────────

def is_paused() -> bool:
    conn = get_connection()
    row = conn.execute("SELECT value FROM system_config WHERE key='paused'").fetchone()
    conn.close()
    return bool(row and row["value"] == "1")


def set_paused(paused: bool):
    conn = get_connection()
    conn.execute(
        "INSERT OR REPLACE INTO system_config (key, value) VALUES ('paused', ?)",
        ("1" if paused else "0",)
    )
    conn.commit()
    conn.close()
