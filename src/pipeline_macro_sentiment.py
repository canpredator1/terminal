import datetime
import os
import re
import sqlite3
import time

import pandas as pd
import requests
from bs4 import BeautifulSoup
from google import genai
from google.genai import types
from tqdm import tqdm

from src.db_schema import DEFAULT_DB_PATH


MODEL_NAME = "gemini-3.1-flash-lite"
REQUEST_SLEEP_SECONDS = 4.1
MAX_ARTICLES_PER_COMPANY = 2
MAX_ARTICLES_PER_SECTOR = 24
MAX_BROAD_ARTICLES_PER_SECTOR = 10
MAX_MARKET_BROAD_ARTICLES = 28
MAX_ARTICLE_CHARS = 2500
MAX_BROAD_ARTICLE_CHARS = 1600
MAX_MARKET_SECTOR_CHARS = 2200

SECTOR_NEWS_KEYWORDS = {
    "assembly": ["assembly", "packaging", "osat", "advanced packaging", "ems"],
    "device": ["device", "display", "sensor", "iot", "security", "wireless charging"],
    "energy": ["energy", "solar", "grid", "power", "hydrogen", "battery", "storage", "renewable", "utility"],
    "equipment": ["equipment", "wfe", "lithography", "etch", "deposition", "metrology", "inspection", "wafer fab"],
    "foundry": ["foundry", "fab", "wafer", "node", "capacity", "process technology"],
    "ip": ["ip", "licensing", "architecture", "arm", "risc-v", "interconnect"],
    "memory": ["memory", "dram", "nand", "hbm", "sram"],
    "semiconductor": ["semiconductor", "chip", "chips", "gpu", "cpu", "ai", "data center", "silicon"],
    "server": ["server", "data center", "datacenter", "rack", "liquid cooling", "ai infrastructure"],
}
MARKET_HEADLINE_KEYWORDS = sorted(
    set().union(*SECTOR_NEWS_KEYWORDS.values())
    | {"chip", "chips", "chipmaker", "chipmakers", "semiconductor", "semiconductors", "tariff", "tariffs", "china", "export", "exports", "inflation", "rates", "fed"}
)


def contains_keyword(text: str, keyword: str) -> bool:
    keyword = keyword.lower()
    if re.fullmatch(r"[a-z0-9]+", keyword) and len(keyword) <= 3:
        return re.search(rf"\b{re.escape(keyword)}\b", text) is not None
    return keyword in text


def contains_any_keyword(text: str, keywords: list[str]) -> bool:
    return any(contains_keyword(text, keyword) for keyword in keywords)

SCORE_COLUMNS = [
    "general_sentiment_score",
    "ai_demand_sentiment",
    "data_center_sentiment",
    "hbm_sentiment",
    "foundry_capacity_sentiment",
    "semiconductor_capex_sentiment",
    "china_export_risk_sentiment",
    "inventory_sentiment",
    "gross_margin_sentiment",
    "pricing_pressure_sentiment",
    "automotive_demand_sentiment",
    "consumer_demand_sentiment",
    "industrial_demand_sentiment",
    "optical_networking_sentiment",
    "memory_pricing_sentiment",
    "analyst_sentiment",
    "management_tone_sentiment",
    "risk_sentiment",
]


ARTICLE_TEXT_CACHE: dict[str, str] = {}


def fetch_article_text(url: str) -> str:
    if not url or not isinstance(url, str):
        return ""
    if url in ARTICLE_TEXT_CACHE:
        return ARTICLE_TEXT_CACHE[url]

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
        )
    }
    try:
        response = requests.get(url, headers=headers, timeout=8)
        response.raise_for_status()
    except Exception:
        ARTICLE_TEXT_CACHE[url] = ""
        return ""

    soup = BeautifulSoup(response.text, "html.parser")
    paragraphs = [
        p.get_text(" ", strip=True)
        for p in soup.find_all("p")
        if len(p.get_text(" ", strip=True)) > 40
    ]
    text = "\n".join(paragraphs)
    ARTICLE_TEXT_CACHE[url] = text
    return text


def format_score_block(row: pd.Series) -> str:
    lines = []
    for col in SCORE_COLUMNS:
        value = row.get(col)
        if pd.notna(value):
            lines.append(f"- {col}: {float(value):.3f}")
    return "\n".join(lines)


def build_company_score_context(df_sector_companies: pd.DataFrame) -> str:
    blocks = []
    for _, row in df_sector_companies.sort_values("ticker").iterrows():
        summary = row.get("sentiment_summary")
        if not isinstance(summary, str) or not summary.strip():
            summary = "No company sentiment summary stored."
        blocks.append(
            "\n".join(
                [
                    f"Company: {row['ticker']} - {row.get('company_name') or row['ticker']}",
                    format_score_block(row),
                    f"Company sentiment summary: {summary}",
                ]
            )
        )
    return "\n\n".join(blocks)


def _dedupe_key(row: pd.Series) -> str:
    url = row.get("url")
    if isinstance(url, str) and url.strip():
        return url.strip().lower()
    return str(row.get("headline") or "").strip().lower()


def _topic_set(row: pd.Series) -> set[str]:
    tags = row.get("topic_tags")
    if not isinstance(tags, str):
        return set()
    return {tag.strip().lower() for tag in tags.split(",") if tag.strip()}


def _matches_sector(row: pd.Series, sector_name: str) -> bool:
    sector = (sector_name or "").lower()
    topics = _topic_set(row)
    headline = f"{row.get('headline') or ''}".lower()
    text = f"{row.get('headline') or ''} {row.get('summary') or ''}".lower()
    headline_has_energy = contains_any_keyword(headline, SECTOR_NEWS_KEYWORDS["energy"])
    headline_has_semiconductor = contains_any_keyword(headline, SECTOR_NEWS_KEYWORDS["semiconductor"])

    if sector == "energy":
        return contains_any_keyword(text, SECTOR_NEWS_KEYWORDS["energy"])

    if "energy" in topics and "semiconductor" not in topics and "macro" not in topics:
        return False
    if headline_has_energy and not headline_has_semiconductor:
        return False

    sector_keywords = SECTOR_NEWS_KEYWORDS.get(sector, [])
    if contains_any_keyword(headline, sector_keywords):
        return True
    if headline_has_semiconductor:
        return True
    if "semiconductor" in topics and contains_any_keyword(headline, MARKET_HEADLINE_KEYWORDS):
        return True
    return False


def _format_article_block(row: pd.Series, evidence_type: str, max_chars: int, fetch_full_text: bool) -> str:
    full_text = fetch_article_text(row.get("url")) if fetch_full_text else ""
    if not full_text:
        full_text = row.get("summary") if isinstance(row.get("summary"), str) else ""
    if not full_text:
        full_text = "Full article text unavailable; use headline/source only."

    return "\n".join(
        [
            f"Evidence type: {evidence_type}",
            f"Stored ticker feed: {row.get('ticker') or ''}",
            f"Headline: {row.get('headline') or ''}",
            f"Source: {row.get('source') or ''}",
            f"Published: {row.get('published_at') or ''}",
            f"URL: {row.get('url') or ''}",
            f"Topic tags: {row.get('topic_tags') or ''}",
            "Article text:",
            full_text[:max_chars],
        ]
    )


def _query_ticker_news(
    conn: sqlite3.Connection,
    tickers: list[str],
    company_specific: bool,
    limit: int,
) -> pd.DataFrame:
    if not tickers:
        return pd.DataFrame()
    placeholders = ",".join("?" for _ in tickers)
    specificity = 1 if company_specific else 0
    return pd.read_sql_query(
        f"""
        SELECT ticker, headline, source, url, published_at, summary, topic_tags
        FROM news_events
        WHERE ticker IN ({placeholders})
          AND is_company_specific = ?
          AND (is_sector_wide = 1 OR is_macro_related = 1 OR is_company_specific = 1)
        ORDER BY published_at DESC
        LIMIT ?
        """,
        conn,
        params=(*tickers, specificity, limit),
    )


def build_news_context(
    conn: sqlite3.Connection,
    tickers: list[str],
    sector_name: str,
    fetch_full_text: bool,
) -> str:
    company_blocks = []
    broad_blocks = []
    seen = set()
    articles_seen = 0

    for ticker in tickers:
        if articles_seen >= MAX_ARTICLES_PER_SECTOR:
            break

        df_news = pd.read_sql_query(
            """
            SELECT ticker, headline, source, url, published_at, summary, topic_tags
            FROM news_events
            WHERE ticker = ? AND is_company_specific = 1
            ORDER BY published_at DESC
            LIMIT ?
            """,
            conn,
            params=(ticker, MAX_ARTICLES_PER_COMPANY),
        )

        for _, row in df_news.iterrows():
            if articles_seen >= MAX_ARTICLES_PER_SECTOR:
                break

            key = _dedupe_key(row)
            if key in seen:
                continue
            seen.add(key)
            company_blocks.append(
                _format_article_block(
                    row,
                    "company-specific sector constituent news",
                    MAX_ARTICLE_CHARS,
                    fetch_full_text,
                )
            )
            articles_seen += 1

    if sector_name == "energy":
        df_broad = pd.read_sql_query(
            """
            SELECT ticker, headline, source, url, published_at, summary, topic_tags
            FROM news_events
            WHERE is_company_specific = 0
              AND (is_sector_wide = 1 OR is_macro_related = 1)
            ORDER BY published_at DESC
            LIMIT ?
            """,
            conn,
            params=(MAX_BROAD_ARTICLES_PER_SECTOR * 4,),
        )
    else:
        df_broad = _query_ticker_news(
            conn,
            tickers,
            company_specific=False,
            limit=MAX_BROAD_ARTICLES_PER_SECTOR * 4,
        )

    for _, row in df_broad.iterrows():
        if len(broad_blocks) >= MAX_BROAD_ARTICLES_PER_SECTOR:
            break
        if not _matches_sector(row, sector_name):
            continue
        key = _dedupe_key(row)
        if key in seen:
            continue
        seen.add(key)
        broad_blocks.append(
            _format_article_block(
                row,
                "broad sector or macro news",
                MAX_BROAD_ARTICLE_CHARS,
                fetch_full_text,
            )
        )

    sections = []
    if company_blocks:
        sections.append("COMPANY-SPECIFIC NEWS FROM SECTOR TICKERS:\n\n" + "\n\n---\n\n".join(company_blocks))
    if broad_blocks:
        sections.append("BROAD SECTOR/MACRO NEWS RELEVANT TO THIS SECTOR:\n\n" + "\n\n---\n\n".join(broad_blocks))
    if not sections:
        return "No recent news evidence was available for this sector."
    return "\n\n====\n\n".join(sections)


def build_market_broad_news_context(conn: sqlite3.Connection, fetch_full_text: bool) -> str:
    df_broad = pd.read_sql_query(
        """
        SELECT ticker, headline, source, url, published_at, summary, topic_tags
        FROM news_events
        WHERE is_company_specific = 0
          AND (is_sector_wide = 1 OR is_macro_related = 1)
        ORDER BY published_at DESC
        LIMIT ?
        """,
        conn,
        params=(MAX_MARKET_BROAD_ARTICLES * 4,),
    )

    blocks = []
    seen = set()
    for _, row in df_broad.iterrows():
        topics = _topic_set(row)
        headline = f"{row.get('headline') or ''}".lower()
        if "semiconductor" not in topics:
            continue
        if not contains_any_keyword(headline, MARKET_HEADLINE_KEYWORDS):
            continue
        key = _dedupe_key(row)
        if key in seen:
            continue
        seen.add(key)
        blocks.append(
            _format_article_block(
                row,
                "deduped broad market evidence",
                MAX_BROAD_ARTICLE_CHARS,
                fetch_full_text,
            )
        )
        if len(blocks) >= MAX_MARKET_BROAD_ARTICLES:
            break

    if not blocks:
        return "No broad semiconductor, energy, or macro news evidence was available."
    return "\n\n---\n\n".join(blocks)


def build_average_context(df: pd.DataFrame, label: str) -> str:
    means = df[SCORE_COLUMNS].mean(numeric_only=True)
    lines = [f"Average sentiment scores for {label}:"]
    for col in SCORE_COLUMNS:
        value = means.get(col)
        if pd.notna(value):
            lines.append(f"- {col}: {float(value):.3f}")
    return "\n".join(lines)


def generate_text(client: genai.Client, prompt: str) -> str:
    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
        config=types.GenerateContentConfig(temperature=0.15),
    )
    return response.text.strip()


def score_strength(value: float) -> str:
    abs_value = abs(float(value))
    if abs_value < 0.15:
        return "weak/neutral"
    if abs_value < 0.30:
        return "modest"
    if abs_value < 0.50:
        return "moderate"
    return "strong"


def _display_score_name(column: str) -> str:
    return column.replace("_sentiment", "").replace("_score", "").replace("_", " ")


def _top_average_themes(df: pd.DataFrame, limit: int = 4) -> list[tuple[str, float]]:
    means = df[SCORE_COLUMNS].mean(numeric_only=True)
    themes = [
        (column, float(means[column]))
        for column in SCORE_COLUMNS
        if column not in {"general_sentiment_score", "risk_sentiment"} and pd.notna(means.get(column))
    ]
    themes.sort(key=lambda item: abs(item[1]), reverse=True)
    return themes[:limit]


def _headline_examples(news_context: str, limit: int = 3) -> list[str]:
    headlines = []
    for headline in re.findall(r"^Headline: (.+)$", news_context, flags=re.MULTILINE):
        headline = headline.strip()
        if headline and headline not in headlines:
            headlines.append(headline)
        if len(headlines) >= limit:
            break
    return headlines


def fallback_sector_overview(sector_name: str, df_sector: pd.DataFrame, news_context: str) -> str:
    means = df_sector[SCORE_COLUMNS].mean(numeric_only=True)
    general = float(means.get("general_sentiment_score", 0) or 0)
    risk = float(means.get("risk_sentiment", 0) or 0)
    themes = _top_average_themes(df_sector, 3)
    theme_text = ", ".join(
        f"{_display_score_name(column)} {score_strength(value)} ({value:.3f})"
        for column, value in themes
    ) or "no dominant thematic signal"

    leaders = df_sector.sort_values("general_sentiment_score", ascending=False).head(3)
    leader_text = ", ".join(
        f"{row['ticker']} ({float(row['general_sentiment_score']):.3f})"
        for _, row in leaders.iterrows()
    )
    headlines = _headline_examples(news_context)
    headline_text = f" Recent evidence includes: {'; '.join(headlines)}." if headlines else ""

    return (
        f"The {sector_name} sector shows {score_strength(general)} general sentiment ({general:.3f}), "
        f"with risk sentiment at {risk:.3f}. The strongest average themes are {theme_text}. "
        f"Company-specific scores are led by {leader_text or 'no clear company leaders'}, so the sector view should be read as grounded in constituent-level evidence rather than a broad unsupported narrative."
        f"{headline_text}"
    )


def fallback_market_overview(df_raw: pd.DataFrame, sector_overviews: list[str], broad_news_context: str) -> str:
    means = df_raw[SCORE_COLUMNS].mean(numeric_only=True)
    general = float(means.get("general_sentiment_score", 0) or 0)
    risk = float(means.get("risk_sentiment", 0) or 0)
    themes = _top_average_themes(df_raw, 4)
    theme_text = ", ".join(
        f"{_display_score_name(column)} {score_strength(value)} ({value:.3f})"
        for column, value in themes
    ) or "no dominant thematic signal"
    headlines = _headline_examples(broad_news_context, 4)
    headline_text = f" Broad evidence includes: {'; '.join(headlines)}." if headlines else ""
    sector_summaries = []
    for sector_context in sector_overviews:
        if "Grounded sector overview:" in sector_context:
            sector_summaries.append(sector_context.split("Grounded sector overview:", 1)[1].strip())
        else:
            sector_summaries.append(sector_context.strip())
    sector_sentences = []
    for summary in sector_summaries[:3]:
        first_sentence = re.split(r"(?<=\.)\s+", summary, maxsplit=1)[0]
        if first_sentence:
            sector_sentences.append(first_sentence)
    sector_text = " ".join(sector_sentences)

    return (
        f"The overall semiconductor market shows {score_strength(general)} general sentiment ({general:.3f}) "
        f"and risk sentiment of {risk:.3f}. Across company scores, the largest repeated themes are {theme_text}. "
        f"Sector evidence remains mixed, so broad claims should be limited to themes repeated across multiple groups."
        f" {sector_text[:900]}{headline_text}"
    )


def generate_macro_sentiment():
    api_key = os.environ.get("GEMINI_API_KEY")
    client = None
    if not api_key:
        print("GEMINI_API_KEY is not set. Using deterministic fallback summaries.")
    else:
        try:
            client = genai.Client(api_key=api_key)
        except Exception as e:
            print(f"Failed to initialize Gemini client: {e}. Using deterministic fallback summaries.")

    conn = sqlite3.connect(DEFAULT_DB_PATH)
    cur = conn.cursor()

    today = datetime.date.today().isoformat()

    query = f"""
    SELECT
        t.ticker,
        t.company_name,
        t.semiconductor_category AS sector,
        s.sentiment_summary,
        {", ".join("s." + col for col in SCORE_COLUMNS)}
    FROM sentiment_daily s
    JOIN ticker_master t ON s.ticker = t.ticker
    WHERE s.date = '{today}'
      AND t.semiconductor_category IS NOT NULL
      AND t.semiconductor_category != ''
    """
    df_raw = pd.read_sql_query(query, conn)

    if df_raw.empty:
        print(f"No company sentiment data found for today ({today}). Please run pipeline_ai_sentiment.py first.")
        conn.close()
        return

    sectors = sorted(df_raw["sector"].dropna().unique())
    print(
        f"Generating grounded macro sentiment for {len(sectors)} sectors "
        f"from company scores plus grouped news evidence..."
    )

    sector_updates = []
    sector_overview_context = []
    fetch_full_text = client is not None

    for sector_name in tqdm(sectors):
        df_sector = df_raw[df_raw["sector"] == sector_name].copy()
        tickers = df_sector["ticker"].dropna().astype(str).tolist()
        sector_average_context = build_average_context(df_sector, f"the {sector_name} sector")
        company_context = build_company_score_context(df_sector)
        news_context = build_news_context(conn, tickers, sector_name, fetch_full_text)

        prompt = f"""
You are a semiconductor sector analyst.

Task: Write the current sector sentiment for the "{sector_name}" sector using ONLY the evidence below.

Evidence package:

1) Sector score averages:
{sector_average_context}

2) Company-level Gemini sentiment scores and summaries:
{company_context}

3) Layered news evidence for this sector:
{news_context}

Rules:
- Ground every conclusion in the supplied company scores, summaries, and news evidence.
- Do not invent causes, demand trends, risks, or catalysts that are not present in the evidence.
- Use score strength literally: below 0.15 is weak/neutral, 0.15-0.29 is modest, 0.30-0.49 is moderate, and 0.50+ is strong.
- Do not call a sector "AI-driven", "strong", or "robust" unless the relevant average score is 0.50 or higher.
- If a theme is driven by only a few companies, describe it as "selected-company" or "company-specific", not sector-wide.
- Company-specific news can explain company scores. Broad sector/macro news can explain sector context. Do not mix these levels.
- Company news and broad news can add evidence, but they must not override weak or moderate sector averages.
- If evidence is weak or sparse, say that clearly.
- Mention the companies or headlines driving the sector view when they matter.
- Write one concise professional paragraph, plain text only.
"""

        try:
            if client is not None:
                overview_text = generate_text(client, prompt)
            else:
                overview_text = fallback_sector_overview(sector_name, df_sector, news_context)
            means = df_sector[SCORE_COLUMNS].mean(numeric_only=True)
            sector_updates.append(
                (
                    today,
                    sector_name,
                    *(float(means[col]) if pd.notna(means.get(col)) else None for col in SCORE_COLUMNS),
                    overview_text,
                )
            )
            sector_overview_context.append(
                f"Sector: {sector_name}\n{sector_average_context}\nGrounded sector overview: {overview_text[:MAX_MARKET_SECTOR_CHARS]}"
            )
            if client is not None:
                time.sleep(REQUEST_SLEEP_SECONDS)
        except Exception as e:
            print(f"Error generating grounded overview for sector {sector_name}: {e}")
            overview_text = fallback_sector_overview(sector_name, df_sector, news_context)
            means = df_sector[SCORE_COLUMNS].mean(numeric_only=True)
            sector_updates.append(
                (
                    today,
                    sector_name,
                    *(float(means[col]) if pd.notna(means.get(col)) else None for col in SCORE_COLUMNS),
                    overview_text,
                )
            )
            sector_overview_context.append(
                f"Sector: {sector_name}\n{sector_average_context}\nGrounded sector overview: {overview_text[:MAX_MARKET_SECTOR_CHARS]}"
            )

    if sector_updates:
        cur.executemany(
            """
            INSERT OR REPLACE INTO sector_sentiment_daily (
                date, sector, general_sentiment_score, ai_demand_sentiment, data_center_sentiment, hbm_sentiment,
                foundry_capacity_sentiment, semiconductor_capex_sentiment, china_export_risk_sentiment, inventory_sentiment,
                gross_margin_sentiment, pricing_pressure_sentiment, automotive_demand_sentiment, consumer_demand_sentiment,
                industrial_demand_sentiment, optical_networking_sentiment, memory_pricing_sentiment, analyst_sentiment,
                management_tone_sentiment, risk_sentiment, sector_overview
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            sector_updates,
        )
        conn.commit()

    print("Generating grounded total semiconductor market macro overview...")

    df_market = df_raw[df_raw["sector"] != "energy"].copy()
    if df_market.empty:
        df_market = df_raw
    market_sector_context = [
        context for context in sector_overview_context
        if not context.lower().startswith("sector: energy")
    ]
    market_average_context = build_average_context(df_market, "the entire semiconductor market")
    market_broad_news_context = build_market_broad_news_context(conn, fetch_full_text)
    market_prompt = f"""
You are a semiconductor macro strategist.

Task: Write the current overall semiconductor market sentiment using ONLY the grounded sector outputs, market-wide score averages, and broad market evidence below.

1) Market-wide score averages:
{market_average_context}

2) Grounded sector outputs:
{chr(10).join(market_sector_context)}

3) Deduped broad semiconductor/energy/macro news evidence:
{market_broad_news_context}

Rules:
- Do not create a new story beyond the sector evidence.
- Identify the broadest themes that are repeated across multiple sectors.
- Identify risks only when the evidence supports them.
- Use broad market evidence only for market-wide context. Do not attribute a broad article to a single company unless the article explicitly names that company.
- Use score strength literally: below 0.15 is weak/neutral, 0.15-0.29 is modest, 0.30-0.49 is moderate, and 0.50+ is strong.
- Do not describe the full market as "AI-driven", "strong", or "robust" unless repeated sector evidence and average scores support that wording.
- If the sector evidence is mixed or sparse, say that clearly.
- Write one concise professional paragraph, plain text only.
"""

    try:
        if client is not None:
            macro_overview_text = generate_text(client, market_prompt)
        else:
            macro_overview_text = fallback_market_overview(df_market, market_sector_context, market_broad_news_context)
        market_row = df_market[SCORE_COLUMNS].mean(numeric_only=True)

        cur.execute(
            """
            INSERT OR REPLACE INTO market_sentiment_daily (
                date, general_sentiment_score, ai_demand_sentiment, data_center_sentiment, hbm_sentiment,
                foundry_capacity_sentiment, semiconductor_capex_sentiment, china_export_risk_sentiment, inventory_sentiment,
                gross_margin_sentiment, pricing_pressure_sentiment, automotive_demand_sentiment, consumer_demand_sentiment,
                industrial_demand_sentiment, optical_networking_sentiment, memory_pricing_sentiment, analyst_sentiment,
                management_tone_sentiment, risk_sentiment, macro_market_overview
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                today,
                *(float(market_row[col]) if pd.notna(market_row.get(col)) else None for col in SCORE_COLUMNS),
                macro_overview_text,
            ),
        )
        conn.commit()
        print("Grounded total market macro overview generated and saved.")
    except Exception as e:
        print(f"Error generating grounded market overview: {e}")
        macro_overview_text = fallback_market_overview(df_market, market_sector_context, market_broad_news_context)
        market_row = df_market[SCORE_COLUMNS].mean(numeric_only=True)
        cur.execute(
            """
            INSERT OR REPLACE INTO market_sentiment_daily (
                date, general_sentiment_score, ai_demand_sentiment, data_center_sentiment, hbm_sentiment,
                foundry_capacity_sentiment, semiconductor_capex_sentiment, china_export_risk_sentiment, inventory_sentiment,
                gross_margin_sentiment, pricing_pressure_sentiment, automotive_demand_sentiment, consumer_demand_sentiment,
                industrial_demand_sentiment, optical_networking_sentiment, memory_pricing_sentiment, analyst_sentiment,
                management_tone_sentiment, risk_sentiment, macro_market_overview
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                today,
                *(float(market_row[col]) if pd.notna(market_row.get(col)) else None for col in SCORE_COLUMNS),
                macro_overview_text,
            ),
        )
        conn.commit()
        print("Fallback total market macro overview generated and saved.")

    conn.close()


if __name__ == "__main__":
    generate_macro_sentiment()
