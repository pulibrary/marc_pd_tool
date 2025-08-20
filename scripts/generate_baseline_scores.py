#!/usr/bin/env python3
"""Generate baseline scores for known matches for regression testing"""

# Standard library imports
from csv import DictReader
from csv import DictWriter
from pathlib import Path

# Local imports
from marc_pd_tool.application.processing.matching._core_matcher import CoreMatcher
from marc_pd_tool.core.domain.publication import Publication
from marc_pd_tool.infrastructure.config import ConfigLoader


def calculate_baseline_scores(input_file: Path, output_file: Path) -> None:
    """Calculate baseline scores for all known matches

    Args:
        input_file: Path to known_matches.csv
        output_file: Path to output CSV with baseline scores
    """
    # Initialize components
    config = ConfigLoader()
    core_matcher = CoreMatcher(config)

    # Read the known matches
    rows = []
    with open(input_file, "r") as f:
        reader = DictReader(f)
        for row in reader:
            # Create Publication objects from the CSV data
            marc_pub = Publication(
                title=row["marc_title_original"],
                author=row["marc_author_original"],
                main_author=row["marc_main_author_original"],
                publisher=row["marc_publisher_original"],
                year=int(row["marc_year"]) if row["marc_year"] else None,
                lccn=row.get("marc_lccn"),
                country_code=row.get("marc_country_code", ""),
                language_code=row.get("marc_language_code", "eng"),
                source_id=row["marc_id"],
            )

            copyright_pub = Publication(
                title=row["match_title"],
                author=row["match_author"],
                main_author="",  # Copyright/renewal records don't have separate main_author
                publisher=row["match_publisher"],
                year=int(row["match_year"]) if row["match_year"] else None,
                lccn="",
                country_code="",
                language_code="eng",
                source_id=row.get("match_source_id", ""),
            )

            # Use CoreMatcher to calculate scores
            match_result = core_matcher.find_best_match_ignore_thresholds(
                marc_pub,
                [copyright_pub],
                year_tolerance=100,  # Large tolerance to ensure we get scores
                minimum_combined_score=0,  # No minimum to get all scores
            )

            if match_result:
                # Extract scores from the match result's nested structure
                scores = match_result["similarity_scores"]
                title_score = scores["title"]
                author_score = scores["author"]
                publisher_score = scores["publisher"]
                combined_score = scores["combined"]
            else:
                # Shouldn't happen but handle gracefully
                title_score = 0.0
                author_score = 0.0
                publisher_score = 0.0
                combined_score = 0.0

            # Calculate year difference if both years exist
            year_diff = None
            if row["marc_year"] and row["match_year"]:
                try:
                    year_diff = abs(int(row["marc_year"]) - int(row["match_year"]))
                except ValueError:
                    pass

            # Add scores to row
            row["baseline_title_score"] = round(title_score, 2)
            row["baseline_author_score"] = round(author_score, 2)
            row["baseline_publisher_score"] = round(publisher_score, 2)
            row["baseline_combined_score"] = combined_score
            row["baseline_year_difference"] = year_diff if year_diff is not None else ""

            rows.append(row)

            # Print progress
            print(
                f"Processed {row['marc_id']}: T={title_score:.1f}, A={author_score:.1f}, P={publisher_score:.1f}, C={combined_score:.1f}"
            )

    # Write output with baseline scores
    if rows:
        fieldnames = list(rows[0].keys())
        with open(output_file, "w", newline="") as f:
            writer = DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        print(f"\nWrote {len(rows)} rows with baseline scores to {output_file}")


if __name__ == "__main__":
    input_path = Path("tests/fixtures/known_matches.csv")
    output_path = Path("tests/fixtures/known_matches_with_baselines.csv")

    calculate_baseline_scores(input_path, output_path)
