"""
Entity resolution: normalize company names so "Tata Motors Ltd" and "Tata Motors" are treated as the same lead.
Used for deduplication in discovery and for consistent display.
"""
import re
from typing import Optional


# Suffixes to strip for canonical form (case-insensitive)
COMPANY_SUFFIXES = [
    r"\s+(?:Pvt\.?|Private)\s+Limited\.?$",
    r"\s+Ltd\.?$",
    r"\s+Limited$",
    r"\s+Corp\.?$",
    r"\s+Corporation\.?$",
    r"\s+Inc\.?$",
    r"\s+Incorporated\.?$",
    r"\s+Co\.?$",
    r"\s+India$",
    r"\s+Ind\.?$",
]


def normalize_company_name(name: Optional[str]) -> str:
    """
    Return a canonical form of the company name for deduplication and display.
    E.g. "Tata Motors Ltd" -> "Tata Motors", "ABC CEMENT LIMITED" -> "Abc Cement"
    """
    if not name or not isinstance(name, str):
        return ""
    s = name.strip()
    for suffix in COMPANY_SUFFIXES:
        s = re.sub(suffix, "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s+", " ", s).strip()
    # Title case for display (optional); for dedup we could use lower()
    return s


def canonical_key_for_dedup(name: Optional[str], raw_text_snippet: str = "") -> str:
    """
    Key for deduplication: normalized company name (lower) + first 80 chars of normalized text.
    Same company + same context = same lead.
    """
    canonical = normalize_company_name(name).lower()
    snippet = (raw_text_snippet or "")[:80].lower()
    return f"{canonical}|{snippet}"
