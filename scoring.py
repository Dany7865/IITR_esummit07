"""
Lead scoring and product recommendation with optional feedback-based weights.
Uses extraction signals and (when available) learned weights from accepted/rejected/converted feedback.
"""
from typing import List, Tuple
from config import HIGH_PRIORITY_THRESHOLD, MEDIUM_PRIORITY_THRESHOLD

try:
    from services.extraction import detect_industry, extract_requirement_clues, PROCUREMENT_SIGNALS, INDUSTRY_SIGNALS
except ImportError:
    try:
        from extraction import detect_industry, extract_requirement_clues, PROCUREMENT_SIGNALS, INDUSTRY_SIGNALS
    except ImportError:
        from .extraction import detect_industry, extract_requirement_clues, PROCUREMENT_SIGNALS, INDUSTRY_SIGNALS

def _nlp_summary(raw_text: str) -> dict:
    """One call to get NLP summary; used for boost, summary, and intent_score."""
    try:
        from services.nlp import summarize_for_scoring
    except ImportError:
        try:
            from nlp import summarize_for_scoring
        except ImportError:
            from .nlp import summarize_for_scoring
    try:
        return summarize_for_scoring(raw_text)
    except Exception:
        return {}


def _nlp_boost(nlp_summary: dict) -> int:
    """Score boost when NLP finds key phrases or entities (max +5)."""
    boost = 0
    if len(nlp_summary.get("key_phrases") or []) >= 2:
        boost += 3
    if (nlp_summary.get("entities") or {}).get("orgs"):
        boost += 2
    return min(5, boost)


def _get_weights():
    """Load learned weights from DB if available; else default 1.0."""
    try:
        from db import get_db
        with get_db() as conn:
            c = conn.cursor()
            c.execute("SELECT industry_or_product, weight_real FROM scoring_weights")
            return {row["industry_or_product"]: row["weight_real"] for row in c.fetchall()}
    except Exception:
        return {}


def analyze_and_score(raw_text: str) -> dict:
    """
    Analyze raw text and return industry, product_recommendations, requirement_clues,
    score, confidence, priority, summary, intent_score. Uses feedback-adjusted weights and NLP.
    """
    text = raw_text.lower()
    weights = _get_weights()
    nlp_summary = _nlp_summary(raw_text)
    intent_score = nlp_summary.get("procurement_intent_score", 0)
    summary = nlp_summary.get("summary") or ""

    score = 0
    industry, product_recommendations = detect_industry(raw_text)
    requirement_clues = extract_requirement_clues(raw_text)

    # Procurement signals
    for sig in PROCUREMENT_SIGNALS:
        if sig in text:
            w = weights.get(f"signal_{sig}", 1.0)
            score += int(15 * w)
            break
    if "expansion" in text or "new plant" in text or "capacity" in text:
        w = weights.get("signal_expansion", 1.0)
        score += int(25 * w)
    if "tender" in text or "rfp" in text or "contract" in text:
        w = weights.get("signal_tender", 1.0)
        score += int(20 * w)

    # Industry match
    ind_w = weights.get(f"industry_{industry}", 1.0)
    if industry != "Unknown":
        score += int(30 * ind_w)
    score += _nlp_boost(nlp_summary)
    # Intent score adds up to 10 points (0–100 -> 0–10)
    score += int(intent_score / 10)
    score = min(100, score)
    confidence = min(95, score + 10)

    if score >= HIGH_PRIORITY_THRESHOLD:
        priority = "HIGH"
    elif score >= MEDIUM_PRIORITY_THRESHOLD:
        priority = "MEDIUM"
    else:
        priority = "LOW"

    return {
        "industry": industry,
        "product_recommendations": product_recommendations,
        "requirement_clues": requirement_clues,
        "score": score,
        "confidence": confidence,
        "priority": priority,
        "summary": summary,
        "intent_score": intent_score,
    }
