import re
from typing import Any


BOILERPLATE_PATTERNS = [
    r"market news and data brought to you by benzinga apis.*",
    r"benzinga does not provide investment advice.*",
    r"all rights reserved.*",
    r"to add benzinga news as your preferred source on google.*",
    r"posted in:.*",
    r"never miss a trade again.*",
    r"this headline only article is a sample of real-time intelligence.*",
]

HEADLINE_ONLY_PATTERNS = [
    "headline only article",
    "sample of real-time intelligence",
    "18 seconds read",
]

GENERIC_MULTI_TICKER_PATTERNS = [
    "whale alerts",
    "today's top stories",
    "stocks moving",
    "pre-market session",
    "premarket session",
    "market update",
]

FINANCE_TERMS = {
    "analyst",
    "buy",
    "capex",
    "cash",
    "china",
    "demand",
    "earnings",
    "eps",
    "factory",
    "guidance",
    "investment",
    "margin",
    "market",
    "price target",
    "revenue",
    "sales",
    "semiconductor",
    "stock",
    "supply",
}


def normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def clean_article_text(text: str) -> str:
    cleaned = normalize_text(text)
    for pattern in BOILERPLATE_PATTERNS:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
    return normalize_text(cleaned)


def _contains_company_reference(text: str, ticker: str, company_terms: list[str]) -> bool:
    ticker = ticker.upper()
    if ticker and re.search(rf"(?<![A-Za-z0-9]){re.escape(ticker)}(?![A-Za-z0-9])", text):
        return True
    lower = text.lower()
    return any(term.lower() in lower for term in company_terms if term)


def classify_article_quality(
    *,
    ticker: str,
    headline: str,
    article_text: str,
    symbols: str = "",
    company_terms: list[str] | None = None,
) -> dict[str, Any]:
    company_terms = company_terms or []
    raw_text = normalize_text(article_text)
    clean_text = clean_article_text(raw_text)
    combined = normalize_text(f"{headline} {clean_text}")
    combined_lower = combined.lower()
    symbols_set = {s.strip().upper() for s in re.split(r"[,;\s]+", symbols or "") if s.strip()}

    has_company_reference = ticker.upper() in symbols_set or _contains_company_reference(
        combined,
        ticker,
        company_terms,
    )
    has_finance_terms = any(term in combined_lower for term in FINANCE_TERMS)
    is_headline_only = any(pattern in combined_lower for pattern in HEADLINE_ONLY_PATTERNS)
    clean_chars = len(clean_text)
    headline_lower = str(headline or "").lower()
    headline_company_reference = _contains_company_reference(str(headline or ""), ticker, company_terms)
    is_generic_multi = (
        (len(symbols_set) >= 5 and not headline_company_reference)
        or any(pattern in headline_lower for pattern in GENERIC_MULTI_TICKER_PATTERNS)
    )
    if is_headline_only:
        quality = "headline_only"
        usable = False
    elif not has_company_reference:
        quality = "not_company_relevant"
        usable = False
    elif clean_chars < 250:
        quality = "boilerplate_only"
        usable = False
    elif is_generic_multi:
        quality = "generic_multi_ticker"
        usable = False
    elif clean_chars < 800:
        quality = "short_text_relevant"
        usable = True
    elif has_finance_terms:
        quality = "full_text_relevant"
        usable = True
    else:
        quality = "short_text_relevant"
        usable = True

    return {
        "article_text_clean": clean_text,
        "article_text_clean_chars": clean_chars,
        "article_quality": quality,
        "article_usable_for_company_sentiment": 1 if usable else 0,
        "article_has_company_reference": 1 if has_company_reference else 0,
        "article_is_generic_multi_ticker": 1 if is_generic_multi else 0,
    }
