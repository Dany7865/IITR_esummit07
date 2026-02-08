"""
Notifications: WhatsApp (Meta Cloud API), FCM mobile push, and logging.
Supports new_lead and assigned notification types; logs all sends for mobile poll.
"""
import json
import requests
import logging
import smtplib
from email.message import EmailMessage
from typing import Optional, List
from config import (
    WHATSAPP_TOKEN, PHONE_ID, DEFAULT_SALES_NUMBER, MIN_CONFIDENCE_TO_NOTIFY,
    NOTIFY_ON_NEW_LEAD, NOTIFY_ON_ASSIGN, MAX_WHATSAPP_BODY, FCM_SERVER_KEY, BASE_URL,
)
from config import SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM, ADMIN_EMAIL


def send_whatsapp(to_number: str, message: str) -> bool:
    """Send WhatsApp message via Meta Cloud API. Returns True if request succeeded."""
    if not to_number or (to_number or "").replace(" ", "").startswith("91XXXXXXXX"):
        return False
    msg = (message or "")[:MAX_WHATSAPP_BODY]
    url = f"https://graph.facebook.com/v18.0/{PHONE_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number.replace("+", "").replace(" ", "").strip(),
        "type": "text",
        "text": {"body": msg},
    }
    logger = logging.getLogger(__name__)
    try:
        logger.debug('WhatsApp send to=%s payload=%s', to_number, payload)
        r = requests.post(url, headers=headers, json=payload, timeout=10)
        logger.debug('WhatsApp response status=%s text=%s', r.status_code, r.text[:1000])
        return r.status_code == 200
    except Exception as exc:
        logger.exception('WhatsApp send exception')
        return False


def send_whatsapp_interactive_buttons(
    to_number: str,
    body_text: str,
    lead_id: int,
) -> bool:
    """
    Send WhatsApp interactive message with buttons: [Accept Lead], [Schedule Visit], [Not Relevant].
    Requires Meta Cloud API with interactive message support. Button reply payloads can be handled by webhook.
    """
    if not to_number or (to_number or "").replace(" ", "").startswith("91XXXXXXXX"):
        return False
    url = f"https://graph.facebook.com/v18.0/{PHONE_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number.replace("+", "").replace(" ", "").strip(),
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": body_text[:1024]},
            "action": {
                "buttons": [
                    {"type": "reply", "reply": {"id": f"accept_{lead_id}", "title": "Accept Lead"}},
                    {"type": "reply", "reply": {"id": f"schedule_{lead_id}", "title": "Schedule Visit"}},
                    {"type": "reply", "reply": {"id": f"reject_{lead_id}", "title": "Not Relevant"}},
                ]
            },
        },
    }
    logger = logging.getLogger(__name__)
    try:
        logger.debug('WhatsApp interactive to=%s payload=%s', to_number, payload)
        r = requests.post(url, headers=headers, json=payload, timeout=10)
        logger.debug('WhatsApp interactive response status=%s text=%s', r.status_code, r.text[:1000])
        return r.status_code == 200
    except Exception:
        logger.exception('WhatsApp interactive exception')
        return False


def send_whatsapp_debug(to_number: str, message: str) -> dict:
    """Send WhatsApp and return debug info: {ok, status_code, text, error} (does not raise)."""
    url = f"https://graph.facebook.com/v18.0/{PHONE_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number.replace("+", "").replace(" ", "").strip(),
        "type": "text",
        "text": {"body": (message or "")[:MAX_WHATSAPP_BODY]},
    }
    logger = logging.getLogger(__name__)
    try:
        logger.debug('WhatsApp debug send to=%s payload=%s', to_number, payload)
        r = requests.post(url, headers=headers, json=payload, timeout=10)
        return {"ok": r.status_code == 200, "status_code": r.status_code, "text": r.text}
    except Exception as exc:
        logger.exception('WhatsApp debug exception')
        return {"ok": False, "error": str(exc)}


def send_whatsapp_interactive_buttons_debug(to_number: str, body_text: str, lead_id: int) -> dict:
    """Send interactive buttons and return debug info."""
    url = f"https://graph.facebook.com/v18.0/{PHONE_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number.replace("+", "").replace(" ", "").strip(),
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": body_text[:1024]},
            "action": {
                "buttons": [
                    {"type": "reply", "reply": {"id": f"accept_{lead_id}", "title": "Accept Lead"}},
                    {"type": "reply", "reply": {"id": f"schedule_{lead_id}", "title": "Schedule Visit"}},
                    {"type": "reply", "reply": {"id": f"reject_{lead_id}", "title": "Not Relevant"}},
                ]
            },
        },
    }
    logger = logging.getLogger(__name__)
    try:
        logger.debug('WhatsApp interactive debug to=%s payload=%s', to_number, payload)
        r = requests.post(url, headers=headers, json=payload, timeout=10)
        return {"ok": r.status_code == 200, "status_code": r.status_code, "text": r.text}
    except Exception as exc:
        logger.exception('WhatsApp interactive debug exception')
        return {"ok": False, "error": str(exc)}


def format_lead_message(dossier: dict, lead_id: Optional[int] = None) -> str:
    """Format a lead dossier as a short WhatsApp message. Truncates to MAX_WHATSAPP_BODY."""
    company = dossier.get("company", "Unknown")
    industry = dossier.get("industry", "—")
    products = dossier.get("product_recommendations", [])
    score = dossier.get("score", 0)
    confidence = dossier.get("confidence", 0)
    priority = dossier.get("priority", "LOW")
    products_str = ", ".join(products[:3]) if products else "—"
    link = f"{BASE_URL}/api/leads/{lead_id}" if lead_id else BASE_URL
    msg = (
        f"🆕 HPCL Lead: {company}\n"
        f"Industry: {industry}\n"
        f"Products: {products_str}\n"
        f"Score: {score}% | Confidence: {confidence}%\n"
        f"Priority: {priority}\n"
        f"View: {link}"
    )
    return msg[:MAX_WHATSAPP_BODY]


def format_assigned_message(dossier: dict, lead_id: Optional[int] = None) -> str:
    """Format 'lead assigned to you' for WhatsApp."""
    company = dossier.get("company", "Unknown")
    industry = dossier.get("industry", "—")
    products = dossier.get("product_recommendations", [])
    products_str = ", ".join(products[:3]) if products else "—"
    link = f"{BASE_URL}/api/leads/{lead_id}" if lead_id else BASE_URL
    msg = (
        f"✅ Lead assigned to you: {company}\n"
        f"Industry: {industry}\n"
        f"Products: {products_str}\n"
        f"Open: {link}"
    )
    return msg[:MAX_WHATSAPP_BODY]


def send_fcm_push(tokens: List[str], title: str, body: str, data: Optional[dict] = None) -> int:
    """
    Send FCM push to a list of device tokens (legacy HTTP). Returns number of successful sends.
    Set FCM_SERVER_KEY in config. For FCM v1 use Firebase Admin SDK instead.
    """
    if not FCM_SERVER_KEY or not tokens:
        return 0
    url = "https://fcm.googleapis.com/fcm/send"
    headers = {
        "Authorization": f"key={FCM_SERVER_KEY}",
        "Content-Type": "application/json",
    }
    sent = 0
    for token in tokens:
        payload = {
            "to": token,
            "notification": {"title": title, "body": body},
            "data": data or {},
        }
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=10)
            if r.status_code == 200:
                sent += 1
        except Exception:
            pass
    return sent


def send_email(to_email: str, subject: str, body: str) -> bool:
    """Send a simple SMTP email. Returns True on success."""
    if not SMTP_HOST or not to_email:
        return False
    try:
        msg = EmailMessage()
        msg['Subject'] = subject
        msg['From'] = SMTP_FROM
        msg['To'] = to_email
        msg.set_content(body)

        if SMTP_USER and SMTP_PASSWORD:
            server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10)
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
            server.quit()
        else:
            # try unauthenticated send
            server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10)
            server.send_message(msg)
            server.quit()
        return True
    except Exception:
        return False


def notify_new_lead(
    dossier: dict,
    lead_id: Optional[int] = None,
    officer_id: Optional[int] = None,
    officer_phone: Optional[str] = None,
) -> dict:
    """
    Send new-lead notification via WhatsApp and (if configured) FCM.
    Logs to notification_log. Returns {whatsapp: bool, push: int, log_id: int}.
    """
    result = {"whatsapp": False, "push": 0, "log_id": None}
    if not NOTIFY_ON_NEW_LEAD:
        return result
    title = f"New lead: {dossier.get('company', 'Unknown')}"
    body = format_lead_message(dossier, lead_id)
    officer_id = officer_id or 0
    try:
        from db import log_notification, get_device_tokens_for_officer
    except ImportError:
        from ..db import log_notification, get_device_tokens_for_officer
    log_id = log_notification(
        officer_id=officer_id,
        channel="whatsapp",
        notification_type="new_lead",
        title=title,
        body=body,
        lead_id=lead_id,
        payload={"lead_id": lead_id, "company": dossier.get("company")},
    )
    result["log_id"] = log_id
    if officer_phone:
        result["whatsapp"] = send_whatsapp(officer_phone, body)
    if officer_id and FCM_SERVER_KEY:
        tokens = [r["token"] for r in get_device_tokens_for_officer(officer_id)]
        result["push"] = send_fcm_push(
            tokens, title, body[:200],
            data={"type": "new_lead", "lead_id": str(lead_id or "")}
        )
    # Email fallback to admin if configured
    result['email'] = False
    if ADMIN_EMAIL and not (result.get('whatsapp') or result.get('push')):
        result['email'] = send_email(ADMIN_EMAIL, title, body)
    return result


def notify_assigned(
    dossier: dict,
    lead_id: Optional[int] = None,
    officer_id: Optional[int] = None,
    officer_phone: Optional[str] = None,
) -> dict:
    """
    Send 'lead assigned to you' via WhatsApp and FCM. Logs to notification_log.
    """
    result = {"whatsapp": False, "push": 0, "log_id": None}
    if not NOTIFY_ON_ASSIGN:
        return result
    title = f"Lead assigned: {dossier.get('company', 'Unknown')}"
    body = format_assigned_message(dossier, lead_id)
    officer_id = officer_id or 0
    try:
        from db import log_notification, get_device_tokens_for_officer
    except ImportError:
        from ..db import log_notification, get_device_tokens_for_officer
    log_id = log_notification(
        officer_id=officer_id,
        channel="whatsapp",
        notification_type="assigned",
        title=title,
        body=body,
        lead_id=lead_id,
        payload={"lead_id": lead_id, "company": dossier.get("company")},
    )
    result["log_id"] = log_id
    if officer_phone:
        result["whatsapp"] = send_whatsapp(officer_phone, body)
    if officer_id and FCM_SERVER_KEY:
        tokens = [r["token"] for r in get_device_tokens_for_officer(officer_id)]
        result["push"] = send_fcm_push(
            tokens, title, body[:200],
            data={"type": "assigned", "lead_id": str(lead_id or "")}
        )
    result['email'] = False
    if ADMIN_EMAIL and not (result.get('whatsapp') or result.get('push')):
        result['email'] = send_email(ADMIN_EMAIL, title, body)
    return result


def should_notify(dossier: dict) -> bool:
    """Whether to send new-lead notification based on confidence and priority."""
    return (
        dossier.get("confidence", 0) >= MIN_CONFIDENCE_TO_NOTIFY
        and dossier.get("priority") in ("HIGH", "MEDIUM")
    )


def notify_officer_whatsapp(phone: str, dossier: dict, lead_id: Optional[int] = None) -> bool:
    """Legacy: send lead notification to sales officer via WhatsApp only."""
    msg = format_lead_message(dossier, lead_id)
    return send_whatsapp(phone, msg)


def send_mobile_push(officer_id: int, title: str, body: str, data: Optional[dict] = None) -> int:
    """
    Send mobile push to all devices registered for this officer (FCM).
    Returns number of devices notified.
    """
    try:
        from db import get_device_tokens_for_officer
    except ImportError:
        from ..db import get_device_tokens_for_officer
    tokens = [r["token"] for r in get_device_tokens_for_officer(officer_id)]
    return send_fcm_push(tokens, title, body, data=data)
