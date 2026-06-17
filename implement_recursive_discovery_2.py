import re

with open('src/relationships.py', 'r') as f:
    content = f.read()

# Add imports
imports = """import html
import os
import re
import time
import urllib.parse
import requests
from dataclasses import dataclass
from functools import lru_cache
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import pandas as pd
import yfinance as yf
from tqdm import tqdm

try:
    import spacy
    nlp = spacy.load("en_core_web_sm")
except Exception:
    nlp = None

from src.tickers import TICKERS"""

content = re.sub(r'import html.*from src\.tickers import TICKERS', imports, content, flags=re.DOTALL)

# Add Ticker Resolution helper
helper = """
@lru_cache(maxsize=1000)
def _resolve_ticker(company_name: str) -> str | None:
    ignore_list = ["the sec", "sec", "fasb", "gaap", "u.s.", "the united states", "inc.", "corp.", "ltd."]
    if company_name.lower() in ignore_list or len(company_name) < 3:
        return None
    try:
        url = f"https://query2.finance.yahoo.com/v1/finance/search?q={urllib.parse.quote(company_name)}"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            data = response.json()
            quotes = data.get("quotes", [])
            if quotes and "symbol" in quotes[0] and not "." in quotes[0]["symbol"]:
                return quotes[0]["symbol"]
    except Exception:
        pass
    return None

def _discover_relationship_rows_for_source("""

content = content.replace("def _discover_relationship_rows_for_source(", helper)


# Modify _discover_relationship_rows_for_source signature
old_sig = """def _discover_relationship_rows_for_source(
    source_profile: CompanyProfile,
    registry: dict[str, CompanyProfile],
    filing_document: FilingDocument,
) -> list[dict[str, Any]]:"""
new_sig = """def _discover_relationship_rows_for_source(
    source_profile: CompanyProfile,
    registry: dict[str, CompanyProfile],
    filing_document: FilingDocument,
) -> tuple[list[dict[str, Any]], set[str]]:"""

content = content.replace(old_sig, new_sig)


# Add NER loop
old_return_1 = """                    best_matches[match_key] = candidate_row

    discovered_rows = list(best_matches.values())
    return _suppress_generic_pair_relations(discovered_rows)"""

new_return_1 = """                    best_matches[match_key] = candidate_row
                    
        if nlp is not None:
            has_keyword = False
            for keywords in RELATION_KEYWORDS.values():
                if any(kw in segment.lower() for kw in keywords):
                    has_keyword = True
                    break
            
            if has_keyword:
                doc = nlp(segment)
                for ent in doc.ents:
                    if ent.label_ == "ORG" and ent.text.lower() not in source_profile.company_name.lower():
                        if len(ent.text) > 3:
                            ticker = _resolve_ticker(ent.text)
                            if ticker and ticker not in registry:
                                new_tickers_discovered.add(ticker)

    discovered_rows = list(best_matches.values())
    return _suppress_generic_pair_relations(discovered_rows), new_tickers_discovered"""

content = content.replace(old_return_1, new_return_1)


# Modify dict init
content = content.replace("best_matches: dict[tuple[str, str], dict[str, Any]] = {}", "best_matches: dict[tuple[str, str], dict[str, Any]] = {}\n    new_tickers_discovered = set()")


# Modify _discover_relationship_rows
old_discover = """def _discover_relationship_rows(registry: dict[str, CompanyProfile]) -> list[dict[str, Any]]:
    filing_cache: dict[str, FilingDocument | None] = {}
    discovered_rows: list[dict[str, Any]] = []

    for source_ticker in tqdm(TICKERS, desc="Scanning filings"):
        source_profile = registry[source_ticker]
        if not source_profile.public_ticker:
            continue

        if source_profile.public_ticker not in filing_cache:
            filing_cache[source_profile.public_ticker] = _load_filing_document(
                source_profile.public_ticker
            )
            time.sleep(0.1)

        filing_document = filing_cache.get(source_profile.public_ticker)
        if filing_document is None:
            continue

        discovered_rows.extend(
            _discover_relationship_rows_for_source(source_profile, registry, filing_document)
        )

    return discovered_rows"""

new_discover = """def _discover_relationship_rows(registry: dict[str, CompanyProfile], max_depth: int = 3) -> list[dict[str, Any]]:
    filing_cache: dict[str, FilingDocument | None] = {}
    discovered_rows: list[dict[str, Any]] = []
    
    current_queue = list(TICKERS)
    scanned_tickers = set()

    for depth in range(max_depth):
        next_queue = set()
        for source_ticker in tqdm(current_queue, desc=f"Scanning filings (Depth {depth+1})"):
            if source_ticker in scanned_tickers:
                continue
            scanned_tickers.add(source_ticker)

            if source_ticker not in registry:
                registry[source_ticker] = CompanyProfile(
                    ticker=source_ticker,
                    company_name=source_ticker,
                    aliases=(source_ticker,),
                    public_ticker=source_ticker
                )

            source_profile = registry[source_ticker]
            if not source_profile.public_ticker:
                continue

            if source_profile.public_ticker not in filing_cache:
                filing_cache[source_profile.public_ticker] = _load_filing_document(
                    source_profile.public_ticker
                )
                time.sleep(0.1)

            filing_document = filing_cache.get(source_profile.public_ticker)
            if filing_document is None:
                continue

            new_rows, new_tickers = _discover_relationship_rows_for_source(
                source_profile, registry, filing_document
            )
            discovered_rows.extend(new_rows)
            
            for t in new_tickers:
                if t not in scanned_tickers:
                    next_queue.add(t)

        current_queue = list(next_queue)
        if not current_queue:
            break

    return discovered_rows"""

content = content.replace(old_discover, new_discover)


with open('src/relationships.py', 'w') as f:
    f.write(content)
print("Patch applied.")
