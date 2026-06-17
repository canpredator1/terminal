"""Build the company relationships dataset for semiconductor and AI companies."""

from __future__ import annotations

from pathlib import Path

from src.relationships import build_company_relationships_dataframe


def main() -> None:
    project_root = Path(__file__).resolve().parent
    output_dir = project_root / "data" / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    relationships_df = build_company_relationships_dataframe()
    output_path = output_dir / "company_relationships.csv"
    relationships_df.to_csv(output_path, index=False)

    rows_needing_review = relationships_df.loc[relationships_df["confidence_score"] <= 3]
    top_strongest = relationships_df.sort_values(
        ["strength_score", "confidence_score", "source_ticker", "target_ticker"],
        ascending=[False, False, True, True],
    ).head(10)

    print("\nRelationship dataset complete.")
    print(f"Relationship count: {len(relationships_df)}")
    print(f"Rows needing review: {len(rows_needing_review)}")

    print("\nTop strongest relations:")
    if top_strongest.empty:
        print("No relations were generated.")
    else:
        preview_columns = [
            "source_ticker",
            "target_ticker",
            "relationship_type",
            "strength_score",
            "confidence_score",
            "evidence_source",
        ]
        print(top_strongest[preview_columns].to_string(index=False))

    print("\nRows needing review preview:")
    if rows_needing_review.empty:
        print("No review rows.")
    else:
        preview_columns = [
            "source_ticker",
            "target_ticker",
            "relationship_type",
            "confidence_score",
            "evidence_source",
        ]
        print(rows_needing_review.head(10)[preview_columns].to_string(index=False))

    print(f"\nOutput file:\n- {output_path}")


if __name__ == "__main__":
    main()
