import argparse
import csv
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from src.article_quality import classify_article_quality


def extract_article_text(url: str) -> str:
    if not url:
        return ""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
        )
    }
    response = requests.get(url, headers=headers, timeout=20)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    for selector in ["script", "style", "nav", "footer", "header", "aside"]:
        for tag in soup.select(selector):
            tag.decompose()

    candidates = []
    for selector in ["article", "[class*='article']", "[class*='story']", "main"]:
        for node in soup.select(selector):
            text = node.get_text(" ", strip=True)
            if len(text) > 250:
                candidates.append(text)

    if candidates:
        return max(candidates, key=len)

    paragraphs = [
        p.get_text(" ", strip=True)
        for p in soup.find_all("p")
        if len(p.get_text(" ", strip=True)) > 30
    ]
    return "\n".join(paragraphs)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch article body text for URLs in a CSV.")
    parser.add_argument("--input-csv", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--url-column", default="url")
    parser.add_argument("--ticker", default="")
    parser.add_argument("--company-terms", default="")
    args = parser.parse_args()

    input_path = Path(args.input_csv)
    output_path = Path(args.output_csv)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    rows = list(csv.DictReader(input_path.open(newline="", encoding="utf-8")))
    fieldnames = list(rows[0].keys()) if rows else []
    quality_fields = [
        "article_text",
        "article_text_chars",
        "article_text_clean",
        "article_text_clean_chars",
        "article_quality",
        "article_usable_for_company_sentiment",
        "article_has_company_reference",
        "article_is_generic_multi_ticker",
        "fetch_status",
        "fetch_error",
    ]
    for field in quality_fields:
        if field not in fieldnames:
            fieldnames.append(field)

    company_terms = [term.strip() for term in args.company_terms.split(",") if term.strip()]

    for row in rows:
        url = row.get(args.url_column, "")
        try:
            text = extract_article_text(url)
            row["article_text"] = text
            row["article_text_chars"] = str(len(text))
            row["fetch_status"] = "ok" if text else "empty"
            row["fetch_error"] = ""
        except Exception as exc:
            row["article_text"] = ""
            row["article_text_chars"] = "0"
            row["fetch_status"] = "error"
            row["fetch_error"] = str(exc)

        quality = classify_article_quality(
            ticker=args.ticker or row.get("ticker", ""),
            headline=row.get("headline") or row.get("title") or "",
            article_text=row.get("article_text", ""),
            symbols=row.get("symbols") or row.get("stocks") or "",
            company_terms=company_terms,
        )
        row.update({key: str(value) for key, value in quality.items()})

    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    ok_count = sum(1 for row in rows if row.get("fetch_status") == "ok")
    print(f"saved_csv: {output_path}")
    print(f"rows: {len(rows)}")
    print(f"ok: {ok_count}")


if __name__ == "__main__":
    main()
