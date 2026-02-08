"""
Web source monitors for lead discovery: news RSS, tenders RSS, GeM, Tenders24, directory.
Fetches raw items (company/title, text, source type, url) for downstream extraction and scoring.
"""
import feedparser
import requests
from urllib.parse import urljoin
from typing import List, Dict, Any


def fetch_news_leads(rss_url, max_entries=15):
    """Fetch leads from news RSS (e.g. Google News search)."""
    feed = feedparser.parse(rss_url)
    leads = []
    for entry in feed.entries[:max_entries]:
        title = entry.get("title", "")
        summary = entry.get("summary", "")
        text = f"{title} {summary}"
        link = entry.get("link", "")
        leads.append({
            "company": title,
            "raw_text": text,
            "source": "news",
            "source_url": link,
        })
    return leads


def fetch_tender_leads(rss_url, max_entries=15):
    """Fetch leads from tender/news RSS (e.g. tenders with fuel, bitumen, marine)."""
    return fetch_news_leads(rss_url, max_entries=max_entries)  # same shape, different URL


def fetch_directory_leads():
    """
    Placeholder for directory scraping (e.g. industry directories, company listings).
    In production: scrape or API from directories, return same shape: company, raw_text, source, source_url.
    """
    return []


def _item(company: str, raw_text: str, source: str, source_url: str = "") -> Dict[str, Any]:
    return {"company": company, "raw_text": raw_text, "source": source, "source_url": source_url}


def fetch_gem_leads(gem_rss_url: str, max_entries: int = 20) -> List[Dict[str, Any]]:
    """
    Fetch leads from Government e-Marketplace (GeM) tender feed.
    Set GEM_RSS_URL in config to a GeM RSS or API endpoint. Same item shape as news.
    """
    if not (gem_rss_url or "").strip():
        return []
    try:
        feed = feedparser.parse(gem_rss_url)
        out = []
        for entry in feed.entries[:max_entries]:
            title = entry.get("title", "")
            summary = entry.get("summary", "")
            text = f"{title} {summary}"
            link = entry.get("link", "")
            out.append(_item(title, text, "gem", link))
        return out
    except Exception:
        return []


def fetch_tenders24_leads(tenders24_url: str, max_entries: int = 20) -> List[Dict[str, Any]]:
    """
    Fetch leads from Tenders24 (or similar) tender feed.
    Set TENDERS24_URL in config. RSS or API returning title/description/link.
    """
    if not (tenders24_url or "").strip():
        return []
    try:
        feed = feedparser.parse(tenders24_url)
        out = []
        for entry in feed.entries[:max_entries]:
            title = entry.get("title", "")
            summary = entry.get("summary", "")
            text = f"{title} {summary}"
            link = entry.get("link", "")
            out.append(_item(title, text, "tenders24", link))
        return out
    except Exception:
        return []


def fetch_all_sources(news_rss_url, tender_rss_url, gem_rss_url="", tenders24_url=""):
    """Aggregate all configured sources into a single list of raw lead items."""
    items = []
    try:
        items.extend(fetch_news_leads(news_rss_url))
    except Exception:
        pass
    try:
        items.extend(fetch_tender_leads(tender_rss_url))
    except Exception:
        pass
    try:
        items.extend(fetch_gem_leads(gem_rss_url or ""))
    except Exception:
        pass
    try:
        items.extend(fetch_tenders24_leads(tenders24_url or ""))
    except Exception:
        pass
    try:
        items.extend(fetch_directory_leads())
    except Exception:
        pass
    return items
