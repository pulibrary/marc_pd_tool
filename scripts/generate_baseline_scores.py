#!/usr/bin/env python3
"""Recalculate baseline scores for known matches and mismatches for regression testing

This script updates the baseline scores in-place on both:
- known_matches_with_baselines.csv (true positives)
- known_mismatches.csv (false positives that were removed)

This allows for manual curation of the ground truth data while being able to
recalculate scores after algorithm improvements.
"""

# Standard library imports
from csv import DictReader
from csv import DictWriter
from pathlib import Path
import shutil

# Local imports
from marc_pd_tool.application.processing.matching._core_matcher import CoreMatcher
from marc_pd_tool.core.domain.publication import Publication
from marc_pd_tool.infrastructure.config import ConfigLoader


def recalculate_baseline_scores(file_path: Path, backup: bool = True) -> None:
    """Recalculate baseline scores for all known matches in-place

    Args:
        file_path: Path to known_matches_with_baselines.csv
        backup: Whether to create a backup before modifying
    """
    # Initialize components
    config = ConfigLoader()
    core_matcher = CoreMatcher(config)

    # Create backup if requested
    if backup:
        backup_path = file_path.with_suffix(".csv.bak")
        shutil.copy2(file_path, backup_path)
        print(f"Created backup at {backup_path}")

    # Read the existing data
    rows = []
    with open(file_path, "r") as f:
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

            # Use the actual copyright LCCN from the data (now that we have it!)
            copyright_lccn = row.get("copyright_lccn", "")

            copyright_pub = Publication(
                title=row["match_title"],
                author=row["match_author"],
                main_author="",  # Copyright/renewal records don't have separate main_author
                publisher=row["match_publisher"],
                year=int(row["match_year"]) if row["match_year"] else None,
                lccn=copyright_lccn,  # Use actual copyright LCCN
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

                # Check if this has LCCN match by comparing actual LCCNs
                has_lccn_match = False
                if marc_pub.lccn and copyright_pub.lccn:
                    # Use normalized LCCNs for comparison like CoreMatcher does
                    marc_lccn = marc_pub.normalized_lccn
                    copyright_lccn = copyright_pub.normalized_lccn
                    has_lccn_match = bool(
                        marc_lccn and copyright_lccn and marc_lccn == copyright_lccn
                    )

                # Check for generic title if detector is enabled
                has_generic = False
                if core_matcher.generic_detector:
                    marc_generic = core_matcher.generic_detector.is_generic(marc_pub.title)
                    copyright_generic = core_matcher.generic_detector.is_generic(
                        copyright_pub.title
                    )
                    has_generic = marc_generic or copyright_generic

                # Calculate different scoring variations to understand impact

                # 1. Score without LCCN boost (but WITH title containment)
                score_without_lccn = core_matcher.score_combiner.combine_scores(
                    title_score,
                    author_score,
                    publisher_score,
                    has_generic_title=has_generic,
                    use_config_weights=True,
                    has_lccn_match=False,  # Force no LCCN boost
                )

                # 2. To get score without title containment, we need to recalculate title score
                # without containment detection
                language = marc_pub.language_code or "eng"

                # Save original containment detection state
                original_check = core_matcher.similarity_calculator._check_title_containment

                # Temporarily disable containment detection
                core_matcher.similarity_calculator._check_title_containment = lambda *args: 0.0

                # Recalculate title score without containment
                title_score_no_containment = (
                    core_matcher.similarity_calculator.calculate_title_similarity(
                        marc_pub.title, copyright_pub.title, language
                    )
                )

                # Restore original containment detection
                core_matcher.similarity_calculator._check_title_containment = original_check

                # 3. Score WITH LCCN boost but WITHOUT title containment
                score_without_containment = core_matcher.score_combiner.combine_scores(
                    title_score_no_containment,
                    author_score,
                    publisher_score,
                    has_generic_title=has_generic,
                    use_config_weights=True,
                    has_lccn_match=has_lccn_match,
                )

                # 4. Score with NEITHER LCCN boost NOR title containment
                score_neither = core_matcher.score_combiner.combine_scores(
                    title_score_no_containment,
                    author_score,
                    publisher_score,
                    has_generic_title=has_generic,
                    use_config_weights=True,
                    has_lccn_match=False,
                )
            else:
                # Shouldn't happen but handle gracefully
                title_score = 0.0
                author_score = 0.0
                publisher_score = 0.0
                combined_score = 0.0
                score_without_lccn = 0.0
                score_without_containment = 0.0
                score_neither = 0.0
                title_score_no_containment = 0.0

            # Calculate year difference if both years exist
            year_diff = None
            if row["marc_year"] and row["match_year"]:
                try:
                    year_diff = abs(int(row["marc_year"]) - int(row["match_year"]))
                except ValueError:
                    pass

            # Update scores in row (preserving all other fields)
            row["baseline_title_score"] = round(title_score, 2)
            row["baseline_author_score"] = round(author_score, 2)
            row["baseline_publisher_score"] = round(publisher_score, 2)
            row["baseline_combined_score"] = combined_score
            row["score_without_lccn_boost"] = score_without_lccn
            row["title_score_no_containment"] = round(title_score_no_containment, 2)
            row["score_without_containment"] = score_without_containment
            row["score_no_lccn_no_containment"] = score_neither
            row["baseline_year_difference"] = year_diff if year_diff is not None else ""

            rows.append(row)

            # Print progress every 100 rows
            if len(rows) % 100 == 0:
                print(f"Processed {len(rows)} rows...")

    # Write updated data back to the same file
    if rows:
        fieldnames = list(rows[0].keys())
        with open(file_path, "w", newline="") as f:
            writer = DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        print(f"\nRecalculated baseline scores for {len(rows)} rows")
        print(f"Updated file: {file_path}")


if __name__ == "__main__":
    # Score both matches and mismatches files
    matches_file = Path("tests/fixtures/known_matches_with_baselines.csv")
    mismatches_file = Path("tests/fixtures/known_mismatches_with_baselines.csv")

    # Process known matches
    if not matches_file.exists():
        print(f"Error: {matches_file} does not exist")
        exit(1)

    print("=" * 60)
    print("Processing KNOWN MATCHES (true positives)")
    print("=" * 60)
    recalculate_baseline_scores(matches_file, backup=True)

    # Process known mismatches if file exists
    if mismatches_file.exists():
        print("\n" + "=" * 60)
        print("Processing KNOWN MISMATCHES (false positives)")
        print("=" * 60)
        recalculate_baseline_scores(mismatches_file, backup=True)
    else:
        print(f"\nNote: {mismatches_file} does not exist - skipping mismatch scoring")
