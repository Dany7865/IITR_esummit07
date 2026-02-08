"""
Feedback loop: record accepted/rejected/converted and update scoring weights
to improve future recommendations.
"""
from collections import defaultdict

try:
    from db import get_db, record_feedback, get_feedback_for_weights
except ImportError:
    get_db = record_feedback = get_feedback_for_weights = None


def record_lead_feedback(lead_id: int, outcome: str, officer_id: int = None, notes: str = None):
    """Record feedback and optionally update weights."""
    if record_feedback:
        record_feedback(lead_id, outcome, officer_id, notes)
    _update_weights_from_feedback()


def _update_weights_from_feedback():
    """
    Compute simple weight adjustments from feedback and persist to scoring_weights.
    Accepted/converted -> boost that industry/signal; Rejected -> slight penalty.
    """
    if not get_db or not get_feedback_for_weights:
        return
    try:
        rows = get_feedback_for_weights()
    except Exception:
        return
    # Aggregate: industry -> list of outcomes
    industry_outcomes = defaultdict(list)
    for r in rows:
        ind = r.get("industry") or "Unknown"
        industry_outcomes[ind].append(r.get("outcome"))
    with get_db() as conn:
        c = conn.cursor()
        for industry, outcomes in industry_outcomes.items():
            accepted = sum(1 for o in outcomes if o in ("Assigned", "Accepted", "Converted"))
            rejected = sum(1 for o in outcomes if o == "Rejected")
            total = len(outcomes)
            if total == 0:
                continue
            # Simple rule: more accepted -> weight 1.2, more rejected -> 0.85
            ratio = accepted / total if total else 0.5
            weight = 0.85 + 0.35 * ratio
            weight = round(weight, 2)
            c.execute(
                """INSERT INTO scoring_weights (industry_or_product, weight_real, signal_type, updated_at)
                   VALUES (?, ?, 'industry', CURRENT_TIMESTAMP)
                   ON CONFLICT(industry_or_product) DO UPDATE SET weight_real = ?, updated_at = CURRENT_TIMESTAMP""",
                (f"industry_{industry}", weight, weight),
            )
