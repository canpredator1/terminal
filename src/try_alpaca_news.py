import argparse
import csv
import os
from datetime import datetime, timezone
from pathlib import Path

import requests


def iso_utc(value: str) -> str:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def main() -> None:
    parser = argparse.ArgumentParser(description="Try one Alpaca historical news request.")
    parser.add_argument("--ticker", default="MU")
    parser.add_argument("--start", default="2023-06-12T00:00:00Z")
    parser.add_argument("--end", default="2023-06-19T00:00:00Z")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--max-pages", type=int, default=1)
    parser.add_argument("--out-csv")
    args = parser.parse_args()

    key_id = os.environ.get("APCA_API_KEY_ID") or os.environ.get("ALPACA_API_KEY")
    secret = os.environ.get("APCA_API_SECRET_KEY") or os.environ.get("ALPACA_SECRET_KEY")
    if not key_id or not secret:
        raise SystemExit(
            "Missing Alpaca credentials. Set APCA_API_KEY_ID and APCA_API_SECRET_KEY first."
        )

    headers = {
        "APCA-API-KEY-ID": key_id,
        "APCA-API-SECRET-KEY": secret,
    }
    news = []
    page_token = None
    last_status = None
    for page in range(args.max_pages):
        params = {
            "symbols": args.ticker.upper(),
            "start": iso_utc(args.start),
            "end": iso_utc(args.end),
            "limit": args.limit,
            "sort": "asc",
        }
        if page_token:
            params["page_token"] = page_token

        response = requests.get(
            "https://data.alpaca.markets/v1beta1/news",
            headers=headers,
            params=params,
            timeout=30,
        )
        last_status = response.status_code
        if response.status_code != 200:
            print("status:", response.status_code)
            print(response.text[:1000])
            response.raise_for_status()

        payload = response.json()
        news.extend(payload.get("news", []))
        page_token = payload.get("next_page_token")
        if not page_token:
            break

    print("status:", last_status)
    print(f"ticker: {args.ticker.upper()}")
    print(f"window: {args.start} to {args.end}")
    print(f"articles: {len(news)}")
    print()
    if args.out_csv:
        output_path = Path(args.out_csv)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "id",
                    "created_at",
                    "updated_at",
                    "headline",
                    "summary",
                    "author",
                    "source",
                    "symbols",
                    "url",
                ],
            )
            writer.writeheader()
            for item in news:
                writer.writerow(
                    {
                        "id": item.get("id"),
                        "created_at": item.get("created_at"),
                        "updated_at": item.get("updated_at"),
                        "headline": item.get("headline"),
                        "summary": item.get("summary"),
                        "author": item.get("author"),
                        "source": item.get("source"),
                        "symbols": ",".join(item.get("symbols") or []),
                        "url": item.get("url"),
                    }
                )
        print(f"saved_csv: {output_path}")

    for i, item in enumerate(news, 1):
        print(f"{i}. {item.get('headline')}")
        print(f"   created_at: {item.get('created_at') or item.get('updated_at')}")
        print(f"   source: {item.get('source')}")
        print(f"   symbols: {', '.join(item.get('symbols') or [])}")
        print(f"   url: {item.get('url')}")
        summary = item.get("summary")
        if summary:
            print(f"   summary: {summary[:300]}")
        print()


if __name__ == "__main__":
    main()
