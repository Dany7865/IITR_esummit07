"""
Data extraction and industry-context analysis.
Extracts requirement clues and industry signals from raw text for scoring and dossier.
Uses NLP (cleaning, key phrases, optional entities) when available.
"""
import re
from typing import List, Tuple

try:
    from services.nlp import clean_text, extract_key_phrases, summarize_for_scoring, expand_text_with_synonyms
except ImportError:
    try:
        from nlp import clean_text, extract_key_phrases, summarize_for_scoring, expand_text_with_synonyms
    except ImportError:
        from .nlp import clean_text, extract_key_phrases, summarize_for_scoring, expand_text_with_synonyms

# Industry and product signal keywords (expandable with NLP/ML later)
INDUSTRY_SIGNALS = {
    "Cement": ["cement", "clinker", "kiln", "grinding", "limestone"],
    "Marine": ["marine", "shipping", "vessel", "port", "bunker", "maritime"],
    "Construction / Roads": ["road", "highway", "bitumen", "asphalt", "paving", "construction", "infrastructure"],
    "Power / Utilities": ["power", "generation", "furnace", "boiler", "industrial fuel", "dg set"],
    "Refinery / Petrochemical": ["refinery", "petrochemical", "cracker", "lube", "specialty product"],
    "Mining / Steel": ["mining", "steel", "iron", "ore", "pellet"],
    "Aviation": ["aviation", "atf", "airport", "jet fuel"],
    "General Industrial": ["industrial", "manufacturing", "tender", "procurement", "supply"],
}

PRODUCT_MAPPING = {
    "Cement": ["Petcoke", "Furnace Oil", "Industrial Fuels"],
    "Marine": ["Marine Fuel", "LSHS", "Bunker"],
    "Construction / Roads": ["Bitumen", "VGB", "Paving Grade"],
    "Power / Utilities": ["Furnace Oil", "LSHS", "Industrial Fuels"],
    "Refinery / Petrochemical": ["Specialty Products", "Lubes", "Feedstocks"],
    "Mining / Steel": ["Industrial Fuels", "Furnace Oil", "Petcoke"],
    "Aviation": ["ATF", "Jet Fuel"],
    "General Industrial": ["Industrial Fuels", "Furnace Oil", "LSHS"],
}

PROCUREMENT_SIGNALS = [
    "tender", "rfp", "rfi", "contract", "procurement", "supply", "requirement",
    "expansion", "capacity", "new plant", "order", "bid", "purchase"
]


def extract_requirement_clues(raw_text: str) -> List[str]:
    """Extract short requirement clues from text for the dossier. Uses NLP key phrases when available."""
    text = clean_text(raw_text).lower()
    clues = []
    for sig in PROCUREMENT_SIGNALS:
        if sig in text:
            clues.append(f"Procurement signal: {sig}")
    for industry, keywords in INDUSTRY_SIGNALS.items():
        for kw in keywords:
            if kw in text:
                clues.append(f"Industry signal: {industry} ({kw})")
                break
    # Add NLP key phrases as requirement clues (e.g. "marine fuel", "cement expansion")
    try:
        key_phrases = extract_key_phrases(raw_text, max_phrases=6)
        for p in key_phrases:
            clues.append(f"Phrase: {p}")
    except Exception:
        pass
    return clues[:14]  # cap for display


def detect_industry(raw_text: str) -> Tuple[str, List[str]]:
    """
    Detect primary industry and list of HPCL product recommendations.
    Uses cleaned text, synonym expansion, and NLP key phrases for better detection.
    Prefers specific industries (Cement, Marine, Construction, etc.) over General Industrial.
    """
    text = clean_text(raw_text).lower()
    text = expand_text_with_synonyms(text)
    # Include key phrases as additional text for matching (e.g. "marine fuel" -> Marine)
    try:
        key_phrases = extract_key_phrases(raw_text, max_phrases=10)
        text = text + " " + " ".join(key_phrases).lower()
    except Exception:
        pass
    # Prefer specific industries: check them first, use General Industrial only as fallback
    specific = [k for k in INDUSTRY_SIGNALS if k != "General Industrial"]
    best_industry = "Unknown"
    best_score = 0
    for industry in specific:
        keywords = INDUSTRY_SIGNALS[industry]
        score = sum(1 for kw in keywords if kw in text)
        if score > best_score:
            best_score = score
            best_industry = industry
    if best_industry == "Unknown":
        keywords = INDUSTRY_SIGNALS["General Industrial"]
        if sum(1 for kw in keywords if kw in text) > 0:
            best_industry = "General Industrial"
    products = PRODUCT_MAPPING.get(best_industry, ["Industrial Fuels"])
    return best_industry, products
