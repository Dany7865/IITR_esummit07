"""
Feedback-loop ML: use Accepted/Rejected/Converted to train a Random Forest that predicts
propensity to convert. Weights which signals (tender vs news, industry, intent) actually lead to conversions.
"""
import json
import os
from pathlib import Path
from typing import List, Dict, Any, Optional

try:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.preprocessing import LabelEncoder
    import numpy as np
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False

# Model path (optional persistence)
BASE_DIR = Path(__file__).resolve().parent.parent
MODEL_PATH = BASE_DIR / "ml_propensity_model.joblib"
ENCODER_PATH = BASE_DIR / "ml_encoders.json"


def _get_training_data() -> tuple:
    """Build feature matrix and labels from leads + lead_feedback."""
    try:
        from db import get_db
    except ImportError:
        from ..db import get_db
    with get_db() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT l.id, l.industry, l.source, l.score, l.confidence, l.intent_score,
                   l.priority, f.outcome
            FROM leads l
            JOIN lead_feedback f ON f.lead_id = l.id
        """)
        rows = [dict(row) for row in c.fetchall()]
    if len(rows) < 5:
        return None, None, None
    # Features: industry (encoded), source (encoded), score, confidence, intent_score, priority (encoded)
    industries = [r["industry"] or "Unknown" for r in rows]
    sources = [r["source"] or "news" for r in rows]
    priorities = [r["priority"] or "LOW" for r in rows]
    outcomes = [r["outcome"] for r in rows]
    # Binary target: Converted or Assigned -> 1, Rejected -> 0
    y = [1 if o in ("Converted", "Assigned", "Accepted") else 0 for o in outcomes]
    X_industry = industries
    X_source = sources
    X_priority = priorities
    X_numeric = [[r["score"] or 0, r["confidence"] or 0, r["intent_score"] or 0] for r in rows]
    return (X_industry, X_source, X_priority, X_numeric), y, rows


def train_propensity_model() -> Dict[str, Any]:
    """
    Train Random Forest on feedback data. Returns feature importances and status.
    Model can be persisted with joblib for reuse.
    """
    if not HAS_SKLEARN:
        return {"ok": False, "error": "sklearn not available"}
    data = _get_training_data()
    if data[0] is None:
        return {"ok": False, "error": "Insufficient feedback data (need at least 5 labeled leads)"}
    (X_ind, X_src, X_pri, X_num), y, rows = data
    le_ind = LabelEncoder()
    le_src = LabelEncoder()
    le_pri = LabelEncoder()
    ind_enc = le_ind.fit_transform(X_ind)
    src_enc = le_src.fit_transform(X_src)
    pri_enc = le_pri.fit_transform(X_pri)
    X = np.hstack([ind_enc.reshape(-1, 1), src_enc.reshape(-1, 1), pri_enc.reshape(-1, 1), np.array(X_numeric)])
    y_arr = np.array(y)
    clf = RandomForestClassifier(n_estimators=50, max_depth=5, random_state=42)
    clf.fit(X, y_arr)
    # Feature names for importances
    feat_names = ["industry", "source", "priority", "score", "confidence", "intent_score"]
    importances = dict(zip(feat_names, clf.feature_importances_.tolist()))
    # Persist encoders and model for predict_propensity
    try:
        import joblib
        joblib.dump({
            "model": clf,
            "le_industry": le_ind,
            "le_source": le_src,
            "le_priority": le_pri,
        }, MODEL_PATH)
        with open(ENCODER_PATH, "w") as f:
            json.dump({
                "classes_industry": le_ind.classes_.tolist(),
                "classes_source": le_src.classes_.tolist(),
                "classes_priority": le_pri.classes_.tolist(),
            }, f)
    except Exception:
        pass
    return {"ok": True, "samples": len(y), "feature_importances": importances}


def predict_propensity(industry: str, source: str, priority: str, score: int, confidence: int, intent_score: int) -> Optional[float]:
    """
    Predict propensity to convert (0-1) for a lead. Returns None if model not trained.
    """
    if not HAS_SKLEARN or not MODEL_PATH.exists():
        return None
    try:
        import joblib
        import numpy as np
        data = joblib.load(MODEL_PATH)
        clf = data["model"]
        le_ind, le_src, le_pri = data["le_industry"], data["le_source"], data["le_priority"]
        ind_enc = le_ind.transform([industry or "Unknown"])[0]
        src_enc = le_src.transform([source or "news"])[0]
        pri_enc = le_pri.transform([priority or "LOW"])[0]
        X = np.array([[ind_enc, src_enc, pri_enc, score, confidence, intent_score]])
        proba = clf.predict_proba(X)[0]
        # Index 1 = positive class (convert/accept)
        return float(proba[1])
    except Exception:
        return None


def update_lead_propensity(lead_id: int, propensity: float) -> None:
    try:
        from db import get_db
        with get_db() as conn:
            c = conn.cursor()
            c.execute("UPDATE leads SET propensity_score = ? WHERE id = ?", (propensity, lead_id))
    except Exception:
        pass
