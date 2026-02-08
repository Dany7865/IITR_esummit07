"""
Lead Dossier builder: company details, requirement clues, product recommendations,
confidence score, suggested sales actions, Signal Fingerprint, and "Why HPCL?" battlecard.
"""
from typing import List, Optional

try:
    from services.signal_engine import fingerprint_signals, get_primary_product_reasoning
    from services.why_hpcl import build_why_hpcl, sales_pitch_script
except ImportError:
    try:
        from signal_engine import fingerprint_signals, get_primary_product_reasoning
        from why_hpcl import build_why_hpcl, sales_pitch_script
    except ImportError:
        from .signal_engine import fingerprint_signals, get_primary_product_reasoning
        from .why_hpcl import build_why_hpcl, sales_pitch_script


def _suggest_actions(priority: str, industry: str, products: List[str]) -> List[str]:
    """Generate suggested sales actions from priority and context."""
    actions = []
    if priority == "HIGH":
        actions.append("Contact within 24–48 hours with product sheet")
        actions.append("Prepare quote for primary product(s)")
    elif priority == "MEDIUM":
        actions.append("Reach out this week; share case studies")
        actions.append("Identify decision-maker")
    else:
        actions.append("Add to nurture list; periodic check")
    actions.append(f"Highlight HPCL capability in: {', '.join(products[:3])}")
    return actions


def build_dossier(
    company: str,
    raw_text: str,
    source: str,
    analysis: dict,
    source_url: Optional[str] = None,
) -> dict:
    """
    Build a Lead Dossier dict for storage and API/notifications.
    analysis must contain: industry, product_recommendations, requirement_clues, score, confidence, priority.
    """
    products = analysis.get("product_recommendations", [])
    priority = analysis.get("priority", "LOW")
    industry = analysis.get("industry", "Unknown")
    actions = _suggest_actions(priority, industry, products)
    summary = analysis.get("summary") or ""
    # Signal fingerprint: event -> products + reasoning
    try:
        signal_fingerprint = fingerprint_signals(raw_text)
        product_reasoning = get_primary_product_reasoning(industry, products)
    except Exception:
        signal_fingerprint = []
        product_reasoning = ""
    # Why HPCL? battlecard
    try:
        why_hpcl = build_why_hpcl(products, industry)
        pitch_script = sales_pitch_script(company, industry, products, summary)
    except Exception:
        why_hpcl = {"primary_headline": "Why HPCL", "primary_points": [], "primary_cta": "", "all_battlecards": []}
        pitch_script = ""
    return {
        "company": company,
        "raw_text": raw_text,
        "source": source,
        "source_url": source_url or "",
        "industry": industry,
        "product_recommendations": products,
        "requirement_clues": analysis.get("requirement_clues", []),
        "score": analysis.get("score", 0),
        "confidence": analysis.get("confidence", 0),
        "priority": priority,
        "suggested_actions": actions,
        "summary": summary,
        "intent_score": analysis.get("intent_score", 0),
        "signal_fingerprint": signal_fingerprint,
        "product_reasoning": product_reasoning,
        "why_hpcl": why_hpcl,
        "sales_pitch_script": pitch_script,
    }
