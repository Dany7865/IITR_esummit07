"""
Database layer for HPCL Lead Discovery.
Schema: leads (full dossier fields), sales_officers, lead_feedback for ML improvement.
"""
import sqlite3
import json
from contextlib import contextmanager
from config import DATABASE_PATH


@contextmanager
def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_db() as conn:
        c = conn.cursor()
        # Leads with full dossier fields
        c.execute("""
            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT,
                company TEXT,
                raw_text TEXT,
                industry TEXT,
                product_recommendations TEXT,
                requirement_clues TEXT,
                score INTEGER,
                confidence INTEGER,
                priority TEXT,
                suggested_actions TEXT,
                status TEXT DEFAULT 'New',
                assigned_officer_id INTEGER,
                source_url TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # NLP fields (summary, intent_score) - add if missing for existing DBs
        for col, typ in [("summary", "TEXT"), ("intent_score", "INTEGER")]:
            try:
                c.execute(f"ALTER TABLE leads ADD COLUMN {col} {typ}")
            except sqlite3.OperationalError:
                pass
        try:
            c.execute("ALTER TABLE leads ADD COLUMN dossier_extras TEXT")
        except sqlite3.OperationalError:
            pass
        try:
            c.execute("ALTER TABLE leads ADD COLUMN propensity_score REAL")
        except sqlite3.OperationalError:
            pass
        # Add optional geographic columns if missing
        try:
            c.execute("ALTER TABLE leads ADD COLUMN latitude REAL")
        except sqlite3.OperationalError:
            pass
        try:
            c.execute("ALTER TABLE leads ADD COLUMN longitude REAL")
        except sqlite3.OperationalError:
            pass
        # Sales officers (for assignment and WhatsApp)
        c.execute("""
            CREATE TABLE IF NOT EXISTS sales_officers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                phone TEXT,
                email TEXT,
                region TEXT,
                is_active INTEGER DEFAULT 1
            )
        """)
        # Feedback: accepted / rejected / converted — used to improve scoring
        c.execute("""
            CREATE TABLE IF NOT EXISTS lead_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_id INTEGER,
                outcome TEXT,
                officer_id INTEGER,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (lead_id) REFERENCES leads(id),
                FOREIGN KEY (officer_id) REFERENCES sales_officers(id)
            )
        """)
        # Optional: store learned weights per industry/product for adaptive scoring
        c.execute("""
            CREATE TABLE IF NOT EXISTS scoring_weights (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                industry_or_product TEXT UNIQUE,
                weight_real REAL,
                signal_type TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Notification log (WhatsApp + push) for mobile to poll and avoid duplicate sends
        c.execute("""
            CREATE TABLE IF NOT EXISTS notification_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                officer_id INTEGER,
                channel TEXT,
                notification_type TEXT,
                title TEXT,
                body TEXT,
                lead_id INTEGER,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                payload TEXT,
                FOREIGN KEY (officer_id) REFERENCES sales_officers(id),
                FOREIGN KEY (lead_id) REFERENCES leads(id)
            )
        """)
        # Device tokens for mobile push (FCM)
        c.execute("""
            CREATE TABLE IF NOT EXISTS device_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                officer_id INTEGER NOT NULL,
                token TEXT NOT NULL,
                platform TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(officer_id, token)
            )
        """)


def seed_if_empty(seed_leads_callback=None):
    """Seed sales_officers if empty. Optionally call seed_leads_callback(conn) to insert sample leads."""
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM sales_officers")
        if c.fetchone()[0] == 0:
            c.execute(
                "INSERT INTO sales_officers (name, phone, region) VALUES (?, ?, ?)",
                ("Default Officer", "91XXXXXXXXXX", "All")
            )
        if seed_leads_callback:
            c.execute("SELECT COUNT(*) FROM leads")
            if c.fetchone()[0] == 0:
                seed_leads_callback(conn)


def insert_lead(conn, dossier):
    c = conn.cursor()
    extras = {
        "signal_fingerprint": dossier.get("signal_fingerprint", []),
        "why_hpcl": dossier.get("why_hpcl", {}),
        "product_reasoning": dossier.get("product_reasoning", ""),
        "sales_pitch_script": dossier.get("sales_pitch_script", ""),
    }
    c.execute("""
        INSERT INTO leads (
            source, company, raw_text, industry, product_recommendations,
            requirement_clues, score, confidence, priority, suggested_actions,
            status, source_url, summary, intent_score, dossier_extras, propensity_score,
            latitude, longitude
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        dossier.get("source"),
        dossier.get("company"),
        dossier.get("raw_text"),
        dossier.get("industry"),
        json.dumps(dossier.get("product_recommendations", [])),
        json.dumps(dossier.get("requirement_clues", [])),
        dossier.get("score", 0),
        dossier.get("confidence", 0),
        dossier.get("priority", "LOW"),
        json.dumps(dossier.get("suggested_actions", [])),
        "New",
        dossier.get("source_url"),
        dossier.get("summary") or "",
        dossier.get("intent_score", 0),
        json.dumps(extras),
        dossier.get("propensity_score"),
        dossier.get("latitude"),
        dossier.get("longitude"),
    ))
    return c.lastrowid


def get_all_leads():
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM leads ORDER BY score DESC, created_at DESC")
        return [dict(row) for row in c.fetchall()]


def get_lead(lead_id):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM leads WHERE id = ?", (lead_id,))
        row = c.fetchone()
        return dict(row) if row else None


def update_lead_status(lead_id, status, assigned_officer_id=None):
    with get_db() as conn:
        c = conn.cursor()
        if assigned_officer_id is not None:
            c.execute(
                "UPDATE leads SET status = ?, assigned_officer_id = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (status, assigned_officer_id, lead_id)
            )
        else:
            c.execute(
                "UPDATE leads SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (status, lead_id)
            )


def record_feedback(lead_id, outcome, officer_id=None, notes=None):
    with get_db() as conn:
        c = conn.cursor()
        c.execute(
            "INSERT INTO lead_feedback (lead_id, outcome, officer_id, notes) VALUES (?, ?, ?, ?)",
            (lead_id, outcome, officer_id, notes)
        )
        c.execute("UPDATE leads SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (outcome, lead_id))


def get_sales_officers():
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM sales_officers WHERE is_active = 1")
        return [dict(row) for row in c.fetchall()]


def get_officer_phone(officer_id):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT phone FROM sales_officers WHERE id = ?", (officer_id,))
        row = c.fetchone()
        return row["phone"] if row else None


def get_feedback_for_weights():
    with get_db() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT l.industry, l.product_recommendations, f.outcome
            FROM lead_feedback f
            JOIN leads l ON l.id = f.lead_id
        """)
        return [dict(row) for row in c.fetchall()]


def log_notification(officer_id, channel, notification_type, title, body, lead_id=None, payload=None):
    with get_db() as conn:
        c = conn.cursor()
        c.execute(
            """INSERT INTO notification_log (officer_id, channel, notification_type, title, body, lead_id, payload)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (officer_id, channel, notification_type, title, body or "", lead_id, json.dumps(payload or {}))
        )
        return c.lastrowid


def get_notifications_for_officer(officer_id, limit=50):
    with get_db() as conn:
        c = conn.cursor()
        c.execute(
            """SELECT id, channel, notification_type, title, body, lead_id, sent_at, payload
               FROM notification_log WHERE officer_id = ? ORDER BY sent_at DESC LIMIT ?""",
            (officer_id, limit)
        )
        return [dict(row) for row in c.fetchall()]


def register_device_token(officer_id, token, platform="android"):
    with get_db() as conn:
        c = conn.cursor()
        c.execute(
            """INSERT INTO device_tokens (officer_id, token, platform) VALUES (?, ?, ?)
               ON CONFLICT(officer_id, token) DO UPDATE SET platform = excluded.platform""",
            (officer_id, token, platform)
        )


def get_device_tokens_for_officer(officer_id):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT token, platform FROM device_tokens WHERE officer_id = ?", (officer_id,))
        return [dict(row) for row in c.fetchall()]


if __name__ == "__main__":
    # Allow running this file directly to (re)create the schema and seed defaults.
    print("Initializing database and seeding defaults...")
    init_db()
    seed_if_empty()
    print("Done.")
