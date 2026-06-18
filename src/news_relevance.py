import re
from typing import Any


COMMON_COMPANY_WORDS = {
    "advanced",
    "american",
    "analog",
    "class",
    "co",
    "company",
    "corp",
    "corporation",
    "group",
    "holdings",
    "inc",
    "incorporated",
    "international",
    "limited",
    "ltd",
    "micro",
    "ordinary",
    "plc",
    "sa",
    "semiconductor",
    "semiconductors",
    "technologies",
    "technology",
}

COMMON_TICKER_WORDS = {"AI", "AM", "BE", "BY", "CAN", "FOR", "GO", "HAS", "HE", "IN", "IT", "ON", "OR", "PI", "RUN", "SO", "TO", "UK", "US", "WE"}

SEMICONDUCTOR_TERMS = {
    "ai",
    "artificial intelligence",
    "advanced packaging",
    "chip",
    "chips",
    "chipmaker",
    "chipmakers",
    "semiconductor",
    "semiconductors",
    "data center",
    "datacenter",
    "foundry",
    "wafer",
    "memory",
    "hbm",
    "gpu",
    "cpu",
    "fab",
    "fabs",
    "lithography",
    "packaging",
    "silicon",
    "wafer fab equipment",
    "wfe",
}

ENERGY_TERMS = {
    "battery",
    "clean energy",
    "electricity",
    "energy",
    "grid",
    "hydrogen",
    "inverter",
    "power",
    "renewable",
    "renewables",
    "residential solar",
    "solar",
    "storage",
    "utility",
    "utilities",
}

MACRO_TERMS = {
    "fed",
    "federal reserve",
    "inflation",
    "interest rate",
    "interest rates",
    "tariff",
    "tariffs",
    "china",
    "export controls",
    "recession",
    "jobs report",
    "treasury",
    "yields",
    "nasdaq",
    "s&p",
}

SECTOR_TERMS = SEMICONDUCTOR_TERMS | ENERGY_TERMS

TOPIC_KEYWORDS = {
    "semiconductor": SEMICONDUCTOR_TERMS,
    "energy": ENERGY_TERMS,
    "macro": MACRO_TERMS,
}

TICKER_ALIASES = {
    "AMD": ["amd", "advanced micro devices"],
    "NVDA": ["nvidia"],
    "INTC": ["intel"],
    "AVGO": ["broadcom"],
    "TSM": ["taiwan semiconductor", "tsmc"],
    "ASML": ["asml"],
    "AMAT": ["applied materials"],
    "LRCX": ["lam research"],
    "KLAC": ["kla"],
    "MU": ["micron"],
    "QCOM": ["qualcomm"],
    "TXN": ["texas instruments"],
    "MRVL": ["marvell"],
    "ADI": ["analog devices"],
    "NXPI": ["nxp"],
    "ON": ["on semiconductor", "onsemi"],
    "ARM": ["arm holdings", "arm"],
    "SMCI": ["super micro computer", "supermicro"],
}


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value).lower()).strip()


def contains_keyword(text: str, keyword: str) -> bool:
    keyword = keyword.lower()
    if re.fullmatch(r"[a-z0-9]+", keyword) and len(keyword) <= 3:
        return re.search(rf"\b{re.escape(keyword)}\b", text) is not None
    return keyword in text


def extract_related_tickers(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        values = value
    else:
        values = re.split(r"[,;\s]+", str(value))
    tickers = []
    for raw in values:
        text = str(raw).strip().upper()
        text = re.sub(r"^[^A-Z0-9.]+|[^A-Z0-9.]+$", "", text)
        if text and re.fullmatch(r"[A-Z][A-Z0-9.]{0,9}", text):
            tickers.append(text)
    return sorted(set(tickers))


def extract_yahoo_related_tickers(content: dict[str, Any]) -> list[str]:
    candidates: list[Any] = []
    for key in ("relatedTickers", "tickers", "symbols"):
        candidates.extend(content.get(key) or [])

    finance = content.get("finance") or {}
    for key in ("stockTickers", "companyTickers"):
        for item in finance.get(key) or []:
            if isinstance(item, dict):
                candidates.append(item.get("symbol") or item.get("ticker"))
            else:
                candidates.append(item)

    return extract_related_tickers(candidates)


def infer_news_topics(headline: str | None, summary: str | None = "") -> list[str]:
    text = normalize_text(f"{headline or ''} {summary or ''}")
    topics = []
    for topic, keywords in TOPIC_KEYWORDS.items():
        if any(contains_keyword(text, keyword) for keyword in keywords):
            topics.append(topic)
    return topics


def _has_uppercase_ticker(ticker: str, text: str) -> bool:
    ticker = ticker.upper()
    if len(ticker) <= 2 or ticker in COMMON_TICKER_WORDS:
        return False
    return re.search(rf"(?<![A-Za-z0-9]){re.escape(ticker)}(?![A-Za-z0-9])", text) is not None


def _company_aliases(ticker: str, company_name: str | None) -> list[str]:
    aliases = list(TICKER_ALIASES.get(ticker.upper(), []))
    company = normalize_text(company_name)
    if company:
        words = re.findall(r"[a-z0-9]+", company)
        distinctive = [w for w in words if len(w) >= 4 and w not in COMMON_COMPANY_WORDS]
        if len(distinctive) >= 2:
            aliases.append(" ".join(distinctive[:3]))
        aliases.extend(distinctive[:2])
    return sorted(set(a for a in aliases if a))


def classify_news(
    ticker: str,
    company_name: str | None,
    headline: str | None,
    summary: str | None = "",
    related_tickers: Any = None,
) -> dict[str, Any]:
    raw_text = f"{headline or ''} {summary or ''}"
    text = normalize_text(raw_text)
    related = extract_related_tickers(related_tickers)
    ticker_upper = ticker.upper()
    topics = infer_news_topics(headline, summary)

    company_specific = ticker_upper in related or _has_uppercase_ticker(ticker_upper, raw_text)
    if not company_specific:
        company_specific = any(contains_keyword(text, alias) for alias in _company_aliases(ticker_upper, company_name))

    sector_wide = any(topic in {"semiconductor", "energy"} for topic in topics)
    macro_related = "macro" in topics

    if company_specific:
        quality = "company_specific"
    elif sector_wide or macro_related:
        quality = "broad_related"
    else:
        quality = "unmatched"

    return {
        "related_tickers": ",".join(related),
        "is_company_specific": 1 if company_specific else 0,
        "is_sector_wide": 1 if sector_wide else 0,
        "is_macro_related": 1 if macro_related else 0,
        "topic_tags": ",".join(topics),
        "data_quality_flag": quality,
    }
