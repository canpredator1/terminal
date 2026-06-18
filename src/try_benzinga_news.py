import argparse
import csv
import os
from pathlib import Path

import requests


def main() -> None:
    parser = argparse.ArgumentParser(description="Try one Benzinga historical news request.")
    parser.add_argument("--ticker", default="MU")
    parser.add_argument("--topics")
    parser.add_argument("--primary", action="store_true")
    parser.add_argument("--date-from", default="2023-06-12")
    parser.add_argument("--date-to", default="2023-06-19")
    parser.add_argument("--page-size", type=int, default=20)
    parser.add_argument("--out-csv")
    args = parser.parse_args()

    token = os.environ.get("BENZINGA_API_KEY") or os.environ.get("BENZINGA_TOKEN")
    if not token:
        raise SystemExit("Missing Benzinga token. Set BENZINGA_API_KEY first.")

    params = {
        "token": token,
        "dateFrom": args.date_from,
        "dateTo": args.date_to,
        "displayOutput": "full",
        "pageSize": args.page_size,
    }
    if args.topics:
        params["topics"] = args.topics
    elif args.primary:
        params["primaryTickers"] = args.ticker.upper()
    else:
        params["tickers"] = args.ticker.upper()

    response = requests.get(
        "https://api.benzinga.com/api/v2/news",
        params=params,
        headers={"accept": "application/json"},
        timeout=30,
    )
    print("status:", response.status_code)
    if response.status_code != 200:
        print(response.text[:1000])
        response.raise_for_status()

    payload = response.json()
    if isinstance(payload, dict):
        articles = payload.get("data") or payload.get("news") or payload.get("articles") or []
    else:
        articles = payload

    print(f"ticker: {args.ticker.upper()}")
    if args.topics:
        print(f"topics: {args.topics}")
    print(f"window: {args.date_from} to {args.date_to}")
    print(f"articles: {len(articles)}")

    if args.out_csv:
        output_path = Path(args.out_csv)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = [
            "id",
            "created",
            "updated",
            "title",
            "teaser",
            "body",
            "author",
            "channels",
            "stocks",
            "url",
        ]
        with output_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for item in articles:
                writer.writerow(
                    {
                        "id": item.get("id"),
                        "created": item.get("created") or item.get("created_at"),
                        "updated": item.get("updated") or item.get("updated_at"),
                        "title": item.get("title") or item.get("headline"),
                        "teaser": item.get("teaser") or item.get("summary"),
                        "body": item.get("body"),
                        "author": item.get("author"),
                        "channels": ",".join(
                            str(c.get("name") if isinstance(c, dict) else c)
                            for c in (item.get("channels") or [])
                        ),
                        "stocks": ",".join(
                            str(s.get("name") or s.get("symbol") if isinstance(s, dict) else s)
                            for s in (item.get("stocks") or item.get("symbols") or [])
                        ),
                        "url": item.get("url"),
                    }
                )
        print(f"saved_csv: {output_path}")

    for i, item in enumerate(articles, 1):
        title = item.get("title") or item.get("headline")
        created = item.get("created") or item.get("created_at")
        url = item.get("url")
        print(f"\n{i}. {title}")
        print(f"   created: {created}")
        print(f"   url: {url}")
        teaser = item.get("teaser") or item.get("summary")
        if teaser:
            print(f"   teaser: {str(teaser)[:300]}")


if __name__ == "__main__":
    main()
