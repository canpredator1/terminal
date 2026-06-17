import ast
import re

with open("src/tickers.py") as f:
    exec(f.read())
# This gives us TICKERS

with open("src/relationships.py", "r") as f:
    content = f.read()

# 1. Remove RELATED_COMPANIES completely
content = re.sub(r"RELATED_COMPANIES = \{.*?\n\}\n\n", "", content, flags=re.DOTALL)

# 2. Update _build_company_registry
old_build = """def _build_company_registry() -> dict[str, CompanyProfile]:
    raw_registry = {**BASE_COMPANIES, **RELATED_COMPANIES}
    registry: dict[str, CompanyProfile] = {}

    for ticker in TICKERS:
        if ticker not in raw_registry:
            raw_registry[ticker] = {
                "company_name": ticker,
                "aliases": [ticker],
                "public_ticker": ticker,
            }

    for ticker, metadata in raw_registry.items():
        aliases = tuple(dict.fromkeys([metadata["company_name"], *metadata["aliases"]]))
        registry[ticker] = CompanyProfile(
            ticker=ticker,
            company_name=metadata["company_name"],
            aliases=aliases,
            public_ticker=metadata.get("public_ticker"),
        )

    return registry"""

new_build = """def _build_company_registry() -> dict[str, CompanyProfile]:
    registry: dict[str, CompanyProfile] = {}

    for ticker in TICKERS:
        if ticker in BASE_COMPANIES:
            metadata = BASE_COMPANIES[ticker]
        else:
            metadata = {
                "company_name": ticker,
                "aliases": [ticker],
                "public_ticker": ticker,
            }

        aliases = tuple(dict.fromkeys([metadata["company_name"], *metadata["aliases"]]))
        registry[ticker] = CompanyProfile(
            ticker=ticker,
            company_name=metadata["company_name"],
            aliases=aliases,
            public_ticker=metadata.get("public_ticker"),
        )

    return registry"""

content = content.replace(old_build, new_build)

# 3. Update MANUAL_SEED_RELATIONSHIPS to only include pairs where both are in TICKERS
seed_match = re.search(r"MANUAL_SEED_RELATIONSHIPS = \[(.*?)\]", content, flags=re.DOTALL)
if seed_match:
    seed_str = seed_match.group(1)
    new_seed_lines = []
    for line in seed_str.split("\n"):
        if not line.strip(): continue
        # Extract tickers from the tuple e.g. ("NVDA", "TSM", ...)
        match = re.search(r'\("([^"]+)",\s*"([^"]+)"', line)
        if match:
            src, tgt = match.groups()
            if src in TICKERS and tgt in TICKERS:
                new_seed_lines.append(line)
        else:
            # If it doesn't match the pattern, just keep it or ignore
            pass
    new_seed_str = "\n".join(new_seed_lines) + "\n"
    content = content.replace(seed_str, "\n" + new_seed_str)

# 4. Clean up COMPANY_TAGS (remove non-TICKERS)
tag_match = re.search(r"COMPANY_TAGS = \{(.*?)\}", content, flags=re.DOTALL)
if tag_match:
    tag_str = tag_match.group(1)
    new_tag_lines = []
    for line in tag_str.split("\n"):
        if not line.strip(): continue
        match = re.search(r'"([^"]+)":', line)
        if match:
            ticker = match.group(1)
            if ticker in TICKERS:
                new_tag_lines.append(line)
    new_tag_str = "\n".join(new_tag_lines) + "\n"
    content = content.replace(tag_str, "\n" + new_tag_str)


with open("src/relationships.py", "w") as f:
    f.write(content)

print("Done refactoring relationships.py")
