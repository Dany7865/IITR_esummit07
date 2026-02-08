"""
NLP layer for HPCL lead discovery: text cleaning, tokenization, key phrase extraction,
and optional entity extraction. Improves industry detection and requirement clues.
"""
import re
from typing import List, Tuple, Optional

# Lazy-loaded NLTK
_nltk_tokenizer = None
_nltk_stop = None


def _ensure_nltk():
    global _nltk_tokenizer, _nltk_stop
    if _nltk_tokenizer is not None:
        return
    try:
        import nltk
        try:
            nltk.data.find("tokenizers/punkt")
        except LookupError:
            nltk.download("punkt", quiet=True)
        try:
            nltk.data.find("corpora/stopwords")
        except LookupError:
            nltk.download("stopwords", quiet=True)
        from nltk import word_tokenize
        from nltk.corpus import stopwords
        _nltk_tokenizer = word_tokenize
        _nltk_stop = set(stopwords.words("english"))
    except Exception:
        _nltk_tokenizer = False
        _nltk_stop = set()


def clean_text(raw: str) -> str:
    """Strip HTML tags, normalize whitespace, and return plain text."""
    if not raw or not isinstance(raw, str):
        return ""
    text = re.sub(r"<[^>]+>", " ", raw)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def get_tokens(text: str, remove_stopwords: bool = True) -> List[str]:
    """Tokenize and optionally remove stopwords. Falls back to regex if NLTK unavailable."""
    text = clean_text(text)
    if not text:
        return []
    _ensure_nltk()
    if _nltk_tokenizer:
        tokens = _nltk_tokenizer(text.lower())
        if remove_stopwords and _nltk_stop:
            tokens = [t for t in tokens if t.isalnum() and t not in _nltk_stop]
        else:
            tokens = [t for t in tokens if t.isalnum()]
        return tokens
    # Fallback: simple regex word tokenization
    tokens = re.findall(r"\b[a-z0-9]{2,}\b", text.lower())
    if remove_stopwords:
        stop = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "is", "are", "was", "were"}
        tokens = [t for t in tokens if t not in stop]
    return tokens


def extract_ngrams(tokens: List[str], n: int) -> List[str]:
    """Return n-grams as space-separated strings."""
    if len(tokens) < n:
        return []
    return [" ".join(tokens[i : i + n]) for i in range(len(tokens) - n + 1)]


def extract_key_phrases(
    raw_text: str,
    max_phrases: int = 12,
    min_freq: int = 1,
) -> List[str]:
    """
    Extract meaningful 2–3 word phrases (e.g. 'marine fuel', 'cement expansion')
    that are likely requirement or industry signals. Uses tokenization and n-grams.
    """
    text = clean_text(raw_text)
    if not text:
        return []
    tokens = get_tokens(text, remove_stopwords=True)
    if len(tokens) < 2:
        return []
    # Build 2-grams and 3-grams
    two = extract_ngrams(tokens, 2)
    three = extract_ngrams(tokens, 3)
    # Score by containing known signal substrings; include synonyms for better recall
    signal_words = {
        "fuel", "cement", "marine", "bitumen", "tender", "supply", "contract",
        "expansion", "industrial", "road", "construction", "shipping", "vessel",
        "procurement", "refinery", "power", "aviation", "mining", "steel",
        "bunkering", "vessels", "bituminous", "asphalt", "petcoke", "furnace",
        "bunker", "maritime", "highway", "paving", "refinery", "lube", "ore",
    }
    def score_phrase(p: str) -> int:
        words = set(p.split())
        return sum(1 for w in signal_words if w in words)

    candidates = [(p, score_phrase(p)) for p in two + three if score_phrase(p) > 0]
    candidates.sort(key=lambda x: -x[1])
    seen = set()
    out = []
    for p, _ in candidates:
        if p in seen:
            continue
        seen.add(p)
        out.append(p)
        if len(out) >= max_phrases:
            break
    return out


def extract_entities(raw_text: str) -> dict:
    """
    Extract organizations and product-like entities. Uses spaCy if available,
    otherwise returns empty dict so extraction still works without it.
    """
    try:
        import spacy
        nlp = getattr(extract_entities, "_nlp", None)
        if nlp is None:
            try:
                nlp = spacy.load("en_core_web_sm")
            except OSError:
                return {}
            extract_entities._nlp = nlp
        doc = nlp(clean_text(raw_text)[:5000])
        orgs = list({e.text.strip() for e in doc.ents if e.label_ == "ORG" and len(e.text.strip()) > 2})
        products = list({e.text.strip() for e in doc.ents if e.label_ == "PRODUCT" and len(e.text.strip()) > 2})
        return {"orgs": orgs[:10], "products": products[:10]}
    except Exception:
        return {}


# Procurement intent: stronger signals get higher weight (0–100)
INTENT_SIGNALS_STRONG = {"tender", "rfp", "rfi", "contract", "procurement", "bid", "order", "purchase"}
INTENT_SIGNALS_MEDIUM = {"expansion", "capacity", "new plant", "supply", "requirement", "fuel supply"}
INTENT_SIGNALS_WEAK = {"announce", "plan", "consider", "seek", "invite", "float"}


def procurement_intent_score(raw_text: str) -> int:
    """
    Score 0–100 how strongly the text signals procurement/buying intent.
    Used to boost lead priority and in dossier.
    """
    text = clean_text(raw_text).lower()
    if not text:
        return 0
    score = 0
    for w in INTENT_SIGNALS_STRONG:
        if w in text:
            score += 25
    for w in INTENT_SIGNALS_MEDIUM:
        if w in text:
            score += 12
    for w in INTENT_SIGNALS_WEAK:
        if w in text:
            score += 5
    return min(100, score)


def _get_sentences(text: str) -> List[str]:
    """Split into sentences (NLTK or regex)."""
    _ensure_nltk()
    if _nltk_tokenizer:
        try:
            import nltk
            sent_tokenize = nltk.sent_tokenize
            return [s.strip() for s in sent_tokenize(text) if s.strip()]
        except Exception:
            pass
    return [s.strip() for s in re.split(r"[.!?]+", text) if s.strip()]


def extractive_summary(raw_text: str, max_sentences: int = 2, max_length: int = 280) -> str:
    """
    Extractive summary: pick sentences that contain the most signal words.
    Good for dossier snippet without an LLM.
    """
    text = clean_text(raw_text)
    if not text:
        return ""
    sentences = _get_sentences(text)
    if not sentences:
        return text[:max_length] + ("…" if len(text) > max_length else "")
    signal_words = {
        "fuel", "cement", "marine", "bitumen", "tender", "supply", "contract",
        "expansion", "industrial", "construction", "shipping", "vessel",
        "procurement", "refinery", "power", "aviation", "mining", "steel",
    }
    def score_sent(s: str) -> int:
        lower = s.lower()
        return sum(1 for w in signal_words if w in lower)

    scored = [(s, score_sent(s)) for s in sentences]
    scored.sort(key=lambda x: -x[1])
    chosen = [s for s, _ in scored[:max_sentences] if s.strip()]
    if not chosen:
        chosen = sentences[:max_sentences]
    summary = " ".join(chosen).strip()
    return summary[:max_length] + ("…" if len(summary) > max_length else "")


def expand_text_with_synonyms(text: str) -> str:
    """
    Append synonym forms of industry/product terms so keyword matching catches
    'bunkering', 'vessels', 'bituminous', etc. Returns original + space + synonym tokens.
    """
    synonyms = {
        "marine": "maritime bunker vessel shipping",
        "fuel": "fuels petcoke furnace bunker",
        "bitumen": "bituminous asphalt paving",
        "cement": "clinker kiln",
        "tender": "tenders rfq rfp bid",
        "construction": "infrastructure highway road",
    }
    extra = []
    lower = text.lower()
    for canonical, syns in synonyms.items():
        if canonical in lower:
            extra.append(syns)
    return text + " " + " ".join(extra) if extra else text


def extract_company_candidates(raw_text: str) -> List[str]:
    """
    Extract possible company/organization names: spaCy ORG entities plus
    regex for patterns like 'X Ltd', 'X Corp', 'X Limited', 'X India'.
    """
    candidates = []
    # Regex: ... Word(s) Ltd / Corp / Limited / India / Pvt
    for m in re.finditer(
        r"\b([A-Z][A-Za-z0-9\s&]+(?:Ltd|Limited|Corp|Corporation|India|Pvt|Co\.?|Inc\.?)\b)",
        raw_text  # use raw to keep caps
    ):
        candidates.append(m.group(1).strip())
    entities = extract_entities(raw_text)
    for org in (entities.get("orgs") or [])[:5]:
        if org and org not in candidates:
            candidates.append(org)
    return candidates[:10]


def summarize_for_scoring(raw_text: str) -> dict:
    """
    One-call NLP summary: cleaned text, tokens, key phrases, optional entities,
    procurement intent score, and extractive summary.
    """
    text = clean_text(raw_text)
    tokens = get_tokens(text, remove_stopwords=True)
    key_phrases = extract_key_phrases(raw_text)
    entities = extract_entities(raw_text)
    intent = procurement_intent_score(raw_text)
    summary = extractive_summary(raw_text)
    return {
        "cleaned_text": text,
        "tokens": tokens,
        "key_phrases": key_phrases,
        "entities": entities,
        "procurement_intent_score": intent,
        "summary": summary,
    }
