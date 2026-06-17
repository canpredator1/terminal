"""Helper script to regenerate relationships_graph_data.json and update relationship_map.html from company_relationships.csv."""

import json
from pathlib import Path
import pandas as pd
import re
from src.relationships import COMPANY_TAGS

def main():
    project_root = Path(__file__).resolve().parent.parent
    csv_path = project_root / "data" / "output" / "company_relationships.csv"
    json_path = project_root / "data" / "output" / "relationships_graph_data.json"
    html_path = project_root / "data" / "output" / "relationship_map.html"

    if not csv_path.exists():
        print(f"Error: {csv_path} does not exist. Run main_relationships.py first.")
        return

    # Load relationships dataframe
    df = pd.read_csv(csv_path)

    # Ensure no CAN relationships exist
    df = df[(df["source_ticker"] != "CAN") & (df["target_ticker"] != "CAN")]

    # Get unique nodes and their names
    nodes_info = {}
    
    # Process sources
    for _, row in df.iterrows():
        s_ticker = row["source_ticker"]
        s_name = row["source_company"]
        if pd.isna(s_name) or s_name == "":
            s_name = s_ticker
        
        # Keep the longest or first valid name
        if s_ticker not in nodes_info or len(str(s_name)) > len(nodes_info[s_ticker]):
            nodes_info[s_ticker] = s_name

        t_ticker = row["target_ticker"]
        t_name = row["target_company"]
        if pd.isna(t_name) or t_name == "":
            t_name = t_ticker
            
        if t_ticker not in nodes_info or len(str(t_name)) > len(nodes_info[t_ticker]):
            nodes_info[t_ticker] = t_name

    # Build nodes JSON list
    nodes_list = []
    for ticker in sorted(nodes_info.keys()):
        company_name = nodes_info[ticker]
        tag = COMPANY_TAGS.get(ticker, "other")
        nodes_list.append({
            "id": ticker,
            "label": ticker,
            "company": company_name,
            "tag": tag
        })

    # Build edges JSON list
    edges_list = []
    for _, row in df.iterrows():
        edges_list.append({
            "from": row["source_ticker"],
            "to": row["target_ticker"],
            "type": row["relationship_type"],
            "direction": row["direction"],
            "strength": int(row["strength_score"]),
            "confidence": int(row["confidence_score"]),
            "evidence": row["evidence_source"]
        })

    graph_data = {
        "nodes": nodes_list,
        "edges": edges_list
    }

    # Save to JSON
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(graph_data, f, ensure_ascii=False)
    print(f"Saved graph data to {json_path}")

    # Read and update HTML map
    if html_path.exists():
        with open(html_path, "r", encoding="utf-8") as f:
            html_content = f.read()

        # Regex pattern to find graphData = ...
        pattern = r"(graphData\s*=\s*)(.*?)(;?\s*\n\s*//\s*--\s*Visibility\s*/\s*Filter\s*--|;\s*\n\s*//\s*--\s*Color\s*schemes|;\s*\n\s*//\s*Connection\s*counts|;\s*\n\s*const\s*svg\s*=)"
        
        # Let's use a simpler match pattern that looks for graphData = ... and replaces it
        # Specifically targeting graphData = {"nodes": ...}
        # In our file, it looks like:
        # 443: let graphData = null;
        # 444: 
        # 445: // -- Load data --
        # 446: graphData = {"nodes": [...], "edges": [...]};
        
        html_content, count = re.subn(
            r"(graphData\s*=\s*)\{.*?(\};?\n)",
            f"graphData = {json.dumps(graph_data, ensure_ascii=False)};\n",
            html_content,
            flags=re.DOTALL
        )

        if count > 0:
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html_content)
            print(f"Successfully updated data in {html_path} ({len(nodes_list)} nodes, {len(edges_list)} edges).")
        else:
            print("Warning: Could not find graphData pattern in HTML file. Writing inline script update failed.")
    else:
        print(f"Warning: HTML file not found at {html_path}")

if __name__ == "__main__":
    main()
