import re

with open('src/relationships.py', 'r') as f:
    content = f.read()

# 1. Add imports at the top
import_str = """import html
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

content = re.sub(r"import html.*?from src\.tickers import TICKERS", import_str, content, flags=re.DOTALL)

# 2. Add ticker resolution helper
ticker_res_str = """
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
            if quotes and "symbol" in quotes[0]:
                return quotes[0]["symbol"]
    except Exception:
        pass
    return None

def _discover_relationship_rows_for_source("""

content = content.replace("def _discover_relationship_rows_for_source(", ticker_res_str)


# 3. Replace _discover_relationship_rows_for_source
old_discover_source = """def _discover_relationship_rows_for_source(
    source_profile: CompanyProfile,
    registry: dict[str, CompanyProfile],
    filing_document: FilingDocument,
) -> list[dict[str, Any]]:
    best_matches: dict[tuple[str, str], dict[str, Any]] = {}

    for segment in filing_document.segments:
        for target_profile in registry.values():
            if target_profile.ticker == source_profile.ticker:
                continue

            has_alias, _alias_count = _contains_alias(segment, target_profile.aliases)
            if not has_alias:
                continue

            allowed_relation_types = _allowed_discovery_relations(
                source_profile.ticker, target_profile.ticker
            )
            if not allowed_relation_types:
                continue

            for relationship_type in DISCOVERY_RELATION_TYPES:
                if relationship_type not in allowed_relation_types:
                    continue

                score, keyword_hits, phrase_bonus = _score_segment(
                    segment, target_profile.aliases, relationship_type
                )
                if score <= 0:
                    continue

                confidence_score = _match_confidence(score, keyword_hits)
                if confidence_score < 4 and phrase_bonus < 3:
                    continue

                candidate_row = {
                    "source_ticker": source_profile.ticker,
                    "source_company": source_profile.company_name,
                    "target_ticker": target_profile.ticker,
                    "target_company": target_profile.company_name,
                    "relationship_type": relationship_type,
                    "direction": _relationship_direction(
                        relationship_type, source_profile.ticker, target_profile.ticker
                    ),
                    "strength_score": _relationship_strength(
                        relationship_type, score, keyword_hits, phrase_bonus
                    ),
                    "confidence_score": confidence_score,
                    "evidence_source": "sec_filing",
                    "evidence_text": _truncate_text(segment),
                    "source_url": filing_document.source_url,
                    "notes": _sec_notes("source", filing_document),
                }

                match_key = (target_profile.ticker, relationship_type)
                current_best = best_matches.get(match_key)
                if current_best is None or _discovered_row_sort_key(candidate_row) > _discovered_row_sort_key(
                    current_best
                ):
                    best_matches[match_key] = candidate_row

    discovered_rows = list(best_matches.values())
    return _suppress_generic_pair_relations(discovered_rows)"""

# Wait, `_allowed_discovery_relations` doesn't exist in my version of the file, I saw `_relationship_direction` directly.
# Let me look closer at lines 820-880.
"""
def _discover_relationship_rows_for_source(
    source_profile: CompanyProfile,
    registry: dict[str, CompanyProfile],
    filing_document: FilingDocument,
) -> tuple[list[dict[str, Any]], set[str]]:
    best_matches: dict[tuple[str, str], dict[str, Any]] = {}
    new_tickers_discovered = set()

    for segment in filing_document.segments:
        # 1. Standard matching against known registry
        for target_profile in registry.values():
            if target_profile.ticker == source_profile.ticker:
                continue

            has_alias, _alias_count = _contains_alias(segment, target_profile.aliases)
            if not has_alias:
                continue

            for relationship_type in DISCOVERY_RELATION_TYPES:
                score, keyword_hits, phrase_bonus = _score_segment(
                    segment, target_profile.aliases, relationship_type
                )
                if score <= 0:
                    continue

                confidence_score = _match_confidence(score, keyword_hits)

                candidate_row = {
                    "source_ticker": source_profile.ticker,
                    "source_company": source_profile.company_name,
                    "target_ticker": target_profile.ticker,
                    "target_company": target_profile.company_name,
                    "relationship_type": relationship_type,
                    "direction": _relationship_direction(relationship_type),
                    "strength_score": _relationship_strength(
                        relationship_type, score, keyword_hits, phrase_bonus
                    ),
                    "confidence_score": confidence_score,
                    "evidence_source": "sec_filing",
                    "evidence_text": _truncate_text(segment),
                    "source_url": filing_document.source_url,
                    "notes": _sec_notes("source", filing_document),
                }

                match_key = (target_profile.ticker, relationship_type)
                current_best = best_matches.get(match_key)
                if current_best is None or _discovered_row_sort_key(candidate_row) > _discovered_row_sort_key(
                    current_best
                ):
                    best_matches[match_key] = candidate_row
        
        # 2. NER to find new companies
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
                        # Too many false positives, only grab very clear ones
                        if len(ent.text) > 3:
                            ticker = _resolve_ticker(ent.text)
                            if ticker and ticker not in registry:
                                new_tickers_discovered.add(ticker)

    discovered_rows = list(best_matches.values())
    return _suppress_generic_pair_relations(discovered_rows), new_tickers_discovered
"""
