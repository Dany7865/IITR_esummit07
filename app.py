"""
HPCL B2B Lead Discovery & Recommendation System.
AI-powered lead discovery from web sources, dossier generation, notifications, and feedback loop.
"""
import os
import sys

# Run-from-anywhere: ensure app directory is on path and cwd so imports and templates/db work
_APP_DIR = os.path.dirname(os.path.abspath(__file__))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)
os.chdir(_APP_DIR)

import json
from datetime import datetime, timezone
from flask import Flask, render_template, render_template_string, request, redirect, url_for, session, jsonify
from config import (
    NEWS_RSS_URL, TENDER_RSS_URL, GEM_RSS_URL, TENDERS24_URL,
    SECRET_KEY, ADMIN_USER, ADMIN_PASSWORD,
    MIN_CONFIDENCE_TO_NOTIFY, WHATSAPP_VERIFY_TOKEN,
)
from db import (
    init_db, get_all_leads, get_lead, update_lead_status, get_sales_officers,
    get_officer_phone, insert_lead, seed_if_empty,
    get_db,
    get_notifications_for_officer, register_device_token,
)
from services.sources import fetch_all_sources
from services.scoring import analyze_and_score
from services.dossier import build_dossier
from services.notifications import (
    notify_new_lead,
    notify_assigned,
    should_notify,
)
from services.feedback import record_lead_feedback
from services.entity_resolution import canonical_key_for_dedup, normalize_company_name

app = Flask(__name__)
app.secret_key = SECRET_KEY


# ---------- Discovery job: run periodically (cron or scheduler) ----------
def run_discovery():
    """Fetch from all sources, score, build dossiers, insert new leads, notify officers. Uses entity resolution for dedup."""
    seen = set()
    leads = get_all_leads()
    existing = {canonical_key_for_dedup(row.get("company"), row.get("raw_text")) for row in leads}
    items = fetch_all_sources(NEWS_RSS_URL, TENDER_RSS_URL, GEM_RSS_URL, TENDERS24_URL)
    officers = get_sales_officers()
    default_phone = officers[0]["phone"] if officers else None
    for item in items:
        key = canonical_key_for_dedup(item.get("company"), item.get("raw_text"))
        if key in existing or key in seen:
            continue
        seen.add(key)
        analysis = analyze_and_score(item.get("raw_text", ""))
        company_name = normalize_company_name(item.get("company")) or item.get("company") or "Unknown"
        dossier = build_dossier(
            company=company_name,
            raw_text=item.get("raw_text", ""),
            source=item.get("source", "news"),
            analysis=analysis,
            source_url=item.get("source_url"),
        )
        # Optional: ML propensity score (if model trained)
        try:
            from services.ml_feedback import predict_propensity
            prop = predict_propensity(
                dossier.get("industry"), dossier.get("source"), dossier.get("priority"),
                dossier.get("score", 0), dossier.get("confidence", 0), dossier.get("intent_score", 0)
            )
            if prop is not None:
                dossier["propensity_score"] = round(prop, 3)
        except Exception:
            pass
        from db import get_db
        with get_db() as conn:
            lead_id = insert_lead(conn, dossier)
        if should_notify(dossier) and officers:
            default_officer = officers[0]
            notify_new_lead(
                dossier,
                lead_id=lead_id,
                officer_id=default_officer["id"],
                officer_phone=default_officer.get("phone"),
            )
    return len(seen)


def seed_leads(conn):
    from services.dossier import build_dossier
    samples = [
        ("ABC Cement Ltd", "Cement expansion tender fuel supply", "news"),
        ("Oceanic Shipping Corp", "Marine fuel contract shipping vessels", "news"),
        ("Highway Infra Projects", "Road construction tender bitumen supply", "tender"),
    ]
    for company, raw_text, source in samples:
        analysis = analyze_and_score(raw_text)
        dossier = build_dossier(company=company, raw_text=raw_text, source=source, analysis=analysis)
        insert_lead(conn, dossier)


# ---------- Auth ----------
@app.route("/login", methods=["GET", "POST"]) 
def login():
    if request.method == "POST":
        u = request.form.get("u", "")
        p = request.form.get("p", "")
        if u == ADMIN_USER and p == ADMIN_PASSWORD:
            session["user"] = u
            return redirect(url_for("home"))
    return """
    <h2>HPCL Lead Discovery – Login</h2>
    <form method="post">
        Username: <input name="u"><br><br>
        Password: <input type="password" name="p"><br><br>
        <button type="submit">Login</button>
    </form>
    """


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


def _lead_row_to_dossier(row):
    out = dict(row)
    if isinstance(out.get("product_recommendations"), str):
        try:
            out["product_recommendations"] = json.loads(out["product_recommendations"])
        except Exception:
            out["product_recommendations"] = []
    if isinstance(out.get("requirement_clues"), str):
        try:
            out["requirement_clues"] = json.loads(out["requirement_clues"])
        except Exception:
            out["requirement_clues"] = []
    if isinstance(out.get("suggested_actions"), str):
        try:
            out["suggested_actions"] = json.loads(out["suggested_actions"])
        except Exception:
            out["suggested_actions"] = []
    # Merge dossier_extras (signal_fingerprint, why_hpcl, product_reasoning, sales_pitch_script)
    extras = out.get("dossier_extras")
    if isinstance(extras, str):
        try:
            extras = json.loads(extras)
        except Exception:
            extras = {}
    if isinstance(extras, dict):
        out["signal_fingerprint"] = extras.get("signal_fingerprint", [])
        out["why_hpcl"] = extras.get("why_hpcl", {})
        out["product_reasoning"] = extras.get("product_reasoning", "")
        out["sales_pitch_script"] = extras.get("sales_pitch_script", "")
    out.pop("dossier_extras", None)
    out.setdefault("propensity_score", None)
    # Freshness score: based on created_at (days old). Newer leads get higher freshness.
    created = out.get("created_at")
    age_days = None
    freshness = None
    try:
        if created:
            # created may be string or datetime
            if isinstance(created, str):
                # try parsing common formats
                try:
                    created_dt = datetime.fromisoformat(created)
                except Exception:
                    try:
                        # fallback common format
                        created_dt = datetime.strptime(created, "%Y-%m-%d %H:%M:%S")
                    except Exception:
                        created_dt = None
            elif isinstance(created, datetime):
                created_dt = created
            else:
                created_dt = None
            if created_dt:
                # normalize tz-less datetimes to UTC
                if created_dt.tzinfo is None:
                    created_dt = created_dt.replace(tzinfo=timezone.utc)
                now = datetime.now(timezone.utc)
                delta = now - created_dt
                age_days = int(delta.total_seconds() // 86400)
                # freshness: linear decay from 100 -> 0 over 20 days
                freshness = max(0, int(100 - (age_days * 5)))
    except Exception:
        age_days = None
        freshness = None
    out["age_days"] = age_days
    out["freshness_score"] = freshness
    return out


# ---------- Dashboard (enterprise frontend) ----------
@app.route("/")
def home():
    if "user" not in session:
        return redirect(url_for("login"))
    leads = get_all_leads()
    dossiers = [_lead_row_to_dossier(row) for row in leads]
    return render_template("dashboard.html", leads=dossiers)


@app.route("/leads/<int:id>")
def lead_dossier(id):
    if "user" not in session:
        return redirect(url_for("login"))
    lead = get_lead(id)
    if not lead:
        return redirect(url_for("home"))
    return render_template("lead_dossier.html", lead=_lead_row_to_dossier(lead))


@app.route("/map")
def map_view():
    if "user" not in session:
        return redirect(url_for("login"))
    return render_template("map.html")


@app.route("/discover")
def discover():
    if "user" not in session:
        return redirect(url_for("login"))
    n = run_discovery()
    return redirect(url_for("home"))

# ---------- Actions (with feedback) ----------
@app.route("/assign/<int:id>")
def assign(id):
    if "user" not in session:
        return redirect(url_for("login"))
    lead = get_lead(id)
    if not lead:
        return redirect(url_for("home"))
    officer_id = request.args.get("officer_id", type=int) or (get_sales_officers() and get_sales_officers()[0]["id"])
    update_lead_status(id, "Assigned", assigned_officer_id=officer_id)
    record_lead_feedback(id, "Assigned", officer_id=officer_id)
    d = _lead_row_to_dossier(lead)
    notify_assigned(
        d,
        lead_id=id,
        officer_id=officer_id,
        officer_phone=get_officer_phone(officer_id),
    )
    return redirect(url_for("home"))


@app.route("/reject/<int:id>")
def reject(id):
    if "user" not in session:
        return redirect(url_for("login"))
    record_lead_feedback(id, "Rejected", notes=request.args.get("notes"))
    return redirect(url_for("home"))


@app.route("/convert/<int:id>")
def convert(id):
    if "user" not in session:
        return redirect(url_for("login"))
    record_lead_feedback(id, "Converted")
    return redirect(url_for("home"))


# ---------- Mobile / API ----------
@app.route("/api/leads")
def api_leads():
    # Server-side filtering: company, industry, min_score, max_score, priority, status, pagination
    company = request.args.get('company')
    industry = request.args.get('industry')
    min_score = request.args.get('min_score', type=int)
    max_score = request.args.get('max_score', type=int)
    priority = request.args.get('priority')
    status = request.args.get('status')
    limit = min(1000, request.args.get('limit', type=int) or 100)
    offset = request.args.get('offset', type=int) or 0

    sql = "SELECT * FROM leads WHERE 1=1"
    params = []
    if company:
        sql += " AND lower(company) LIKE ?"
        params.append(f"%{company.lower()}%")
    if industry:
        sql += " AND lower(industry) LIKE ?"
        params.append(f"%{industry.lower()}%")
    if min_score is not None:
        sql += " AND score >= ?"
        params.append(min_score)
    if max_score is not None:
        sql += " AND score <= ?"
        params.append(max_score)
    if priority:
        sql += " AND priority = ?"
        params.append(priority.upper())
    if status:
        sql += " AND status = ?"
        params.append(status)
    sql += " ORDER BY score DESC, created_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    with get_db() as conn:
        c = conn.cursor()
        c.execute(sql, params)
        rows = [dict(r) for r in c.fetchall()]
    return jsonify([_lead_row_to_dossier(row) for row in rows])


@app.route("/api/leads/<int:id>")
def api_lead(id):
    lead = get_lead(id)
    if not lead:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_lead_row_to_dossier(lead))


@app.route("/api/leads/<int:id>", methods=["PATCH", "PUT"])
def api_update_lead(id):
    lead = get_lead(id)
    if not lead:
        return jsonify({"error": "Not found"}), 404
    data = request.get_json() or {}
    status = data.get("status")
    if status in ("New", "Assigned", "Rejected", "Converted", "Accepted"):
        update_lead_status(id, status, assigned_officer_id=data.get("assigned_officer_id"))
        record_lead_feedback(id, status, officer_id=data.get("assigned_officer_id"), notes=data.get("notes"))
        return jsonify(_lead_row_to_dossier(get_lead(id)))
    return jsonify({"error": "Invalid status"}), 400


@app.route("/api/geocode", methods=["POST"])
def api_geocode_batch():
    """Geocode leads missing latitude/longitude using Nominatim (OpenStreetMap).
    POST body: { limit: 50 } (optional). Requires login (basic admin session).
    """
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json() or {}
    limit = min(200, int(data.get("limit")) if data.get("limit") else 50)
    user_agent = f"hpcl-lead-geocoder/1.0 ({request.host})"
    import urllib.parse, urllib.request, time
    updated = 0
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT id, company, source_url FROM leads WHERE latitude IS NULL OR longitude IS NULL LIMIT ?", (limit,))
        rows = c.fetchall()
        for row in rows:
            company = (row.get("company") or "").strip()
            query = company or (row.get("source_url") or "")
            if not query:
                continue
            q = urllib.parse.quote_plus(query + " India")
            url = f"https://nominatim.openstreetmap.org/search?q={q}&format=json&limit=1"
            req = urllib.request.Request(url, headers={"User-Agent": user_agent})
            try:
                with urllib.request.urlopen(req, timeout=10) as resp:
                    j = json.loads(resp.read().decode())
                    if j:
                        lat = float(j[0]["lat"]) ; lon = float(j[0]["lon"])
                        c.execute("UPDATE leads SET latitude = ?, longitude = ? WHERE id = ?", (lat, lon, row["id"]))
                        updated += 1
            except Exception as e:
                print("geocode error", query, e)
            time.sleep(1)  # be polite to Nominatim
    return jsonify({"ok": True, "updated": updated})


@app.route("/api/geocode/<int:lead_id>", methods=["POST"])
def api_geocode_single(lead_id):
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    user_agent = f"hpcl-lead-geocoder/1.0 ({request.host})"
    import urllib.parse, urllib.request
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT id, company, source_url FROM leads WHERE id = ?", (lead_id,))
        row = c.fetchone()
        if not row:
            return jsonify({"error": "Not found"}), 404
        query = (row.get("company") or row.get("source_url") or "").strip()
        if not query:
            return jsonify({"ok": False, "error": "No query"}), 400
        q = urllib.parse.quote_plus(query + " India")
        url = f"https://nominatim.openstreetmap.org/search?q={q}&format=json&limit=1"
        req = urllib.request.Request(url, headers={"User-Agent": user_agent})
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                j = json.loads(resp.read().decode())
                if j:
                    lat = float(j[0]["lat"]) ; lon = float(j[0]["lon"])
                    c.execute("UPDATE leads SET latitude = ?, longitude = ? WHERE id = ?", (lat, lon, lead_id))
                    return jsonify({"ok": True, "lat": lat, "lon": lon})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500
    return jsonify({"ok": False})


@app.route("/api/officers")
def api_officers():
    return jsonify(get_sales_officers())


@app.route("/api/device-token", methods=["POST"])
def api_register_device_token():
    """Register FCM device token for an officer (mobile app). Body: { officer_id, token, platform? }."""
    data = request.get_json() or {}
    officer_id = data.get("officer_id")
    token = data.get("token")
    if not officer_id or not token:
        return jsonify({"error": "officer_id and token required"}), 400
    platform = (data.get("platform") or "android").lower()
    register_device_token(officer_id, token, platform)
    return jsonify({"ok": True})


@app.route("/api/whatsapp/send-buttons/<int:lead_id>", methods=["POST"])
def api_whatsapp_send_buttons(lead_id):
    """Send WhatsApp interactive message with [Accept Lead], [Schedule Visit], [Not Relevant] for demo."""
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    lead = get_lead(lead_id)
    if not lead:
        return jsonify({"error": "Lead not found"}), 404
    data = request.get_json() or {}
    to_number = data.get("to") or (get_sales_officers() and get_sales_officers()[0].get("phone"))
    if not to_number:
        return jsonify({"error": "No phone number"}), 400
    d = _lead_row_to_dossier(lead)
    from services.notifications import format_lead_message, send_whatsapp_interactive_buttons_debug
    body = format_lead_message(d, lead_id)
    info = send_whatsapp_interactive_buttons_debug(to_number, body, lead_id)
    # Return debug info to the UI so user can see HTTP status / response
    return jsonify(info)


# ---------- WhatsApp webhook (Meta: verify + button replies) ----------
@app.route("/api/whatsapp/webhook", methods=["GET"])
def whatsapp_webhook_verify():
    """Meta Cloud API webhook verification. Set this URL in Meta Developer Console."""
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token == WHATSAPP_VERIFY_TOKEN:
        return challenge or ""
    return "Forbidden", 403


@app.route("/api/whatsapp/webhook", methods=["POST"])
def whatsapp_webhook_incoming():
    """Handle incoming WhatsApp messages (e.g. button reply: Accept Lead / Schedule Visit / Not Relevant)."""
    try:
        data = request.get_json() or {}
        if data.get("object") != "whatsapp_business_account":
            return jsonify({"ok": True})
        for entry in data.get("entry", []):
            for change in entry.get("changes", []):
                val = change.get("value", {})
                for msg in val.get("messages", []):
                    interactive = (msg.get("interactive") or {}).get("button_reply")
                    if not interactive:
                        continue
                    reply_id = (interactive.get("id") or "").strip()
                    # reply_id is e.g. accept_5, schedule_5, reject_5
                    if reply_id.startswith("accept_"):
                        lead_id = int(reply_id.replace("accept_", ""))
                        update_lead_status(lead_id, "Assigned")
                        record_lead_feedback(lead_id, "Assigned")
                    elif reply_id.startswith("schedule_"):
                        lead_id = int(reply_id.replace("schedule_", ""))
                        update_lead_status(lead_id, "Assigned")
                        record_lead_feedback(lead_id, "Assigned", notes="Schedule visit requested via WhatsApp")
                    elif reply_id.startswith("reject_"):
                        lead_id = int(reply_id.replace("reject_", ""))
                        record_lead_feedback(lead_id, "Rejected", notes="Not relevant via WhatsApp")
    except Exception:
        pass
    return jsonify({"ok": True})


@app.route("/api/ml/train", methods=["POST"])
def api_ml_train():
    """Train propensity model from feedback. Call after SO swipes (Accept/Reject) to improve scoring."""
    try:
        from services.ml_feedback import train_propensity_model
        result = train_propensity_model()
        return jsonify(result)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/notifications")
def api_notifications():
    """List notifications for an officer (mobile app). Query: officer_id=, limit=50."""
    officer_id = request.args.get("officer_id", type=int)
    if officer_id is None:
        return jsonify({"error": "officer_id required"}), 400
    limit = min(100, request.args.get("limit", type=int) or 50)
    rows = get_notifications_for_officer(officer_id, limit=limit)
    out = []
    for r in rows:
        item = dict(r)
        if isinstance(item.get("payload"), str):
            try:
                item["payload"] = json.loads(item["payload"])
            except Exception:
                item["payload"] = {}
        out.append(item)
    return jsonify(out)


@app.route("/notifications")
def notifications_inbox():
    """In-app notification list for an officer (web). Use ?officer_id=1 or pick from dropdown."""
    if "user" not in session:
        return redirect(url_for("login"))
    officer_id = request.args.get("officer_id", type=int)
    officers = get_sales_officers()
    if not officers:
        return render_template_string(
            "<p>No sales officers. <a href='/'>Dashboard</a></p>"
        )
    if officer_id is None:
        officer_id = officers[0]["id"]
    rows = get_notifications_for_officer(officer_id, limit=50)
    notifications = []
    for r in rows:
        item = dict(r)
        if isinstance(item.get("payload"), str):
            try:
                item["payload"] = json.loads(item["payload"]) or {}
            except Exception:
                item["payload"] = {}
        notifications.append(item)
    officer_options = "".join(
        f'<option value="{o["id"]}" {"selected" if o["id"] == officer_id else ""}>{o.get("name", "Officer")} (ID {o["id"]})</option>'
        for o in officers
    )
    items_html = ""
    for n in notifications:
        lead_id = (n.get("payload") or {}).get("lead_id")
        link = f'<a href="/api/leads/{lead_id}">{n.get("title", "—")}</a>' if lead_id else n.get("title", "—")
        items_html += f"""
        <div class="notif-card">
            <div class="notif-type">{n.get("notification_type", "—")}</div>
            <div class="notif-title">{link}</div>
            <div class="notif-body">{n.get("body", "")[:200]}{"…" if len(n.get("body") or "") > 200 else ""}</div>
            <div class="notif-time">{n.get("sent_at", "")}</div>
        </div>
        """
    html = f"""
    <html><head><meta charset="utf-8">
    <style>
    body {{ font-family: system-ui, Arial, sans-serif; background: #f0f2f5; padding: 24px; }}
    .nav {{ margin-bottom: 16px; }} .nav a {{ margin-right: 12px; }}
    .picker {{ margin-bottom: 16px; }} .picker select {{ padding: 8px 12px; }}
    .notif-card {{ background: #fff; padding: 14px; margin-bottom: 10px; border-radius: 10px; box-shadow: 0 1px 4px rgba(0,0,0,0.08); }}
    .notif-type {{ font-size: 12px; color: #666; text-transform: uppercase; margin-bottom: 4px; }}
    .notif-title {{ font-weight: 600; margin-bottom: 6px; }} .notif-title a {{ color: #1a73e8; text-decoration: none; }}
    .notif-body {{ font-size: 14px; color: #444; margin-bottom: 6px; white-space: pre-wrap; }}
    .notif-time {{ font-size: 12px; color: #888; }}
    </style></head><body>
    <h1>Notification inbox</h1>
    <div class="nav"><a href="/">Dashboard</a> <a href="/api/notifications?officer_id={officer_id}">JSON</a></div>
    <form class="picker" method="get" action="/notifications">
        <label>Officer: </label>
        <select name="officer_id" onchange="this.form.submit()">{officer_options}</select>
    </form>
    <p>{len(notifications)} notification(s)</p>
    <div class="list">{items_html or "<p>No notifications yet.</p>"}</div>
    </body></html>
    """
    return render_template_string(html)


# ---------- Init ----------
if __name__ == "__main__":
    init_db()
    seed_if_empty(seed_leads_callback=seed_leads)
    # Robust port probing to avoid "An attempt was made to access a socket in a way
    # forbidden by its access permissions" (WinError 10013) and other bind errors.
    import socket

    ports_to_try = [5000, 5001, 8000, 8080]
    hosts_to_try = ["127.0.0.1", "0.0.0.0"]

    def _port_is_free(host, port):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((host, port))
            s.close()
            return True, None
        except OSError as e:
            try:
                s.close()
            except Exception:
                pass
            return False, e

    started = False
    for host in hosts_to_try:
        for port in ports_to_try:
            free, err = _port_is_free(host, port)
            if free:
                print(f"Attempting to start server on {host}:{port}")
                try:
                    app.run(debug=True, port=port, host=host, use_reloader=False)
                    started = True
                    break
                except Exception as e:
                    import traceback
                    print(f"app.run failed for {host}:{port} — {e}")
                    print(traceback.format_exc())
                    # try next port/host
                    continue
            else:
                # Common Windows permission error is WinError 10013
                if "10013" in str(err) or "WinError 10013" in str(err) or "permission" in str(err).lower():
                    print(f"Port {port} on {host} blocked (permission). Trying next port/host. Error: {err}")
                else:
                    print(f"Port {port} on {host} not available. Trying next. Error: {err}")
        if started:
            break

    if not started:
        # Last resort: let OS pick an ephemeral port on localhost
        try:
            print("No common ports available; attempting ephemeral port on localhost (port=0).")
            # Acquire an ephemeral port by binding with port=0, then use that port.
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("127.0.0.1", 0))
            ephemeral_port = s.getsockname()[1]
            s.close()
            print(f"Ephemeral port chosen: {ephemeral_port}")
            try:
                app.run(debug=True, port=ephemeral_port, host="127.0.0.1", use_reloader=False)
            except Exception as e:
                import traceback
                print(f"app.run failed on ephemeral port {ephemeral_port} — {e}")
                print(traceback.format_exc())
                raise
        except OSError as e:
            print("Failed to bind to any port. If you're on Windows, try: 1) run as Administrator, 2) check firewall/antivirus rules, or 3) pick a different port manually. Error:", e)
            raise
