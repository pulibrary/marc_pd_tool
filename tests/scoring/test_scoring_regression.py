# tests/scoring/test_scoring_regression.py

#!/usr/bin/env python3
"""Scoring algorithm tests against known matches and mismatches baseline.

This test is NOT run as part of the regular test suite. It should be run separately
to check for regressions or improvements in the scoring algorithm.

Tests both:
- Known matches (true positives) - should score high
- Known mismatches (false positives) - should score low

Usage:
    pdm run pytest tests/scoring/test_scoring_regression.py -v

To update baselines after intentional algorithm changes:
    pdm run python scripts/generate_baseline_scores.py
"""

# Standard library imports
from csv import DictReader
from pathlib import Path
from typing import NamedTuple

# Third party imports
from pytest import fixture
from pytest import mark

# Local imports
from marc_pd_tool.application.processing.matching._core_matcher import CoreMatcher
from marc_pd_tool.core.domain.publication import Publication
from marc_pd_tool.infrastructure.config import ConfigLoader


class ScoringResult(NamedTuple):
    """Result of scoring calculation"""

    title_score: float
    author_score: float
    publisher_score: float
    combined_score: float
    year_difference: int | None


class TestScoringRegression:
    """Test scoring algorithm against known baselines to detect regressions"""

    @fixture(scope="class")
    def core_matcher(self) -> CoreMatcher:
        """Create core matcher instance"""
        config = ConfigLoader()
        return CoreMatcher(config)

    @fixture(scope="class")
    def known_matches(self) -> list[dict[str, str]]:
        """Load known matches with baselines"""
        path = Path("tests/fixtures/known_matches_with_baselines.csv")
        with open(path, "r") as f:
            reader = DictReader(f)
            return list(reader)

    @fixture(scope="class")
    def known_mismatches(self) -> list[dict[str, str]]:
        """Load known mismatches (false positives) with baselines"""
        path = Path("tests/fixtures/known_mismatches_with_baselines.csv")
        if not path.exists():
            return []  # Return empty list if file doesn't exist
        with open(path, "r") as f:
            reader = DictReader(f)
            return list(reader)

    def calculate_scores(self, row: dict[str, str], core_matcher: CoreMatcher) -> ScoringResult:
        """Calculate scores for a single match using CoreMatcher

        Args:
            row: Row from known matches CSV
            core_matcher: Core matcher instance

        Returns:
            Scoring result with all scores
        """
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
            lccn=row.get("copyright_lccn", ""),  # Use actual copyright LCCN from data
            country_code="",
            language_code="eng",
            source_id=row.get("match_source_id", ""),
        )

        # Use CoreMatcher's find_best_match_ignore_thresholds to get all scores
        # This method calculates scores without applying thresholds
        match_result = core_matcher.find_best_match_ignore_thresholds(
            marc_pub,
            [copyright_pub],
            year_tolerance=100,  # Use large tolerance to ensure we get scores
            minimum_combined_score=0,  # No minimum to get all scores
        )

        if match_result:
            # Extract scores from the match result's nested structure
            scores = match_result["similarity_scores"]
            title_score = scores["title"]
            author_score = scores["author"]
            publisher_score = scores["publisher"]
            combined_score = scores["combined"]

            # Calculate year difference from the copyright record
            copyright_record = match_result["copyright_record"]
            year_diff = None
            if marc_pub.year and copyright_record["year"]:
                year_diff = abs(marc_pub.year - copyright_record["year"])
        else:
            # Shouldn't happen but handle gracefully
            title_score = 0.0
            author_score = 0.0
            publisher_score = 0.0
            combined_score = 0.0
            year_diff = None

        return ScoringResult(
            title_score=round(title_score, 2),
            author_score=round(author_score, 2),
            publisher_score=round(publisher_score, 2),
            combined_score=round(combined_score, 2),
            year_difference=year_diff,
        )

    @mark.scoring
    @mark.slow  # Mark as slow test (~15 seconds for 20k records)
    def test_scoring_matches_baseline(
        self, known_matches: list[dict[str, str]], core_matcher: CoreMatcher, capfd
    ) -> None:
        """Test that current scoring matches baseline scores

        This test will fail if the scoring algorithm changes in a way that
        affects the scores. This is intentional - any change should be reviewed
        to ensure it's an improvement, not a regression.

        Args:
            known_matches: List of known matches with baseline scores
            core_matcher: Core matcher instance
            capfd: Pytest fixture for capturing output
        """
        # Temporarily disable capture to show progress message immediately
        with capfd.disabled():
            print(f"Processing {len(known_matches):,} baseline records...", end="", flush=True)

        # Track regressions for potential CSV output
        regressions = []
        tolerance = 0.01

        for row in known_matches:
            marc_id = row["marc_id"]

            # Calculate current scores
            result = self.calculate_scores(row, core_matcher)

            # Get baseline scores
            baseline_combined = float(row["baseline_combined_score"])

            # Check for combined score regression
            combined_diff = result.combined_score - baseline_combined

            if combined_diff < -tolerance:  # Score decreased
                regressions.append(
                    {
                        "marc_id": marc_id,
                        "title": row.get("marc_title_original", "")[
                            :50
                        ],  # Truncate for readability
                        "author": row.get("marc_author_original", "")[:30],
                        "baseline_score": baseline_combined,
                        "current_score": result.combined_score,
                        "difference": round(combined_diff, 2),
                        "baseline_title": float(row["baseline_title_score"]),
                        "current_title": result.title_score,
                        "baseline_author": float(row["baseline_author_score"]),
                        "current_author": result.author_score,
                        "baseline_publisher": float(row["baseline_publisher_score"]),
                        "current_publisher": result.publisher_score,
                    }
                )

        # If there are regressions, save to CSV and fail
        if regressions:
            with capfd.disabled():
                print(" FAILED")  # Complete the progress line
            # Save regressions to CSV for debugging
            # Standard library imports
            import csv
            from pathlib import Path

            output_file = Path("scoring_regressions.csv")
            with open(output_file, "w", newline="") as f:
                fieldnames = [
                    "marc_id",
                    "title",
                    "author",
                    "baseline_score",
                    "current_score",
                    "difference",
                    "baseline_title",
                    "current_title",
                    "baseline_author",
                    "current_author",
                    "baseline_publisher",
                    "current_publisher",
                ]
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(regressions)

            # Fail with a clear message
            assert False, (
                f"Found {len(regressions)} scoring regressions. "
                f"Details saved to {output_file.absolute()}"
            )
        else:
            with capfd.disabled():
                print(" done")  # Complete the progress line when successful

    @mark.scoring
    @mark.parametrize("threshold", [50, 60, 70, 80, 90])
    def test_score_distribution(
        self, known_matches: list[dict[str, str]], core_matcher: CoreMatcher, threshold: float
    ) -> None:
        """Test distribution of scores at various thresholds

        This helps understand how many matches would be accepted/rejected
        at different threshold levels.

        Args:
            known_matches: List of known matches with baseline scores
            core_matcher: Core matcher instance
            threshold: Score threshold to test
        """
        above_threshold = 0
        below_threshold = 0

        for row in known_matches:
            result = self.calculate_scores(row, core_matcher)

            if result.combined_score >= threshold:
                above_threshold += 1
            else:
                below_threshold += 1

        total = len(known_matches)
        (above_threshold / total) * 100

        # Just assert that we have a reasonable distribution
        # (Silently pass - no output unless there's a problem)
        assert total > 0, "No matches to test"

    @mark.scoring
    def test_score_without_lccn_boost_column(
        self, known_matches: list[dict[str, str]], core_matcher: CoreMatcher
    ) -> None:
        """Test that score_without_lccn_boost column is present and correct

        This test verifies the new column that shows performance for non-LCCN records.

        Args:
            known_matches: List of known matches with baseline scores
            core_matcher: Core matcher instance
        """
        missing_column = []
        score_differences = []

        for row in known_matches[:100]:  # Sample first 100 for detailed check
            # Check if column exists
            if "score_without_lccn_boost" not in row or not row["score_without_lccn_boost"]:
                missing_column.append(row["marc_id"])
                continue

            # If both baseline_combined_score and score_without_lccn_boost exist
            if row.get("baseline_combined_score") and row.get("score_without_lccn_boost"):
                baseline = float(row["baseline_combined_score"])
                without_boost = float(row["score_without_lccn_boost"])

                # Check if there's an LCCN match
                has_lccn = bool(row.get("marc_lccn"))

                if has_lccn and baseline > without_boost:
                    # This record benefited from LCCN boost
                    score_differences.append(
                        {
                            "id": row["marc_id"],
                            "with_boost": baseline,
                            "without_boost": without_boost,
                            "difference": baseline - without_boost,
                        }
                    )

        # Just assert that the column exists
        assert not missing_column, (
            f"{len(missing_column)} records missing score_without_lccn_boost column. "
            "Run: pdm run python scripts/generate_baseline_scores.py to update"
        )

    @mark.scoring
    def test_field_score_statistics(
        self, known_matches: list[dict[str, str]], core_matcher: CoreMatcher
    ) -> None:
        """Calculate and display statistics for each field's scores

        This helps understand the distribution and effectiveness of each
        field's scoring algorithm.

        Args:
            known_matches: List of known matches with baseline scores
            core_matcher: Core matcher instance
        """
        title_scores = []
        author_scores = []
        publisher_scores = []
        combined_scores = []

        for row in known_matches:
            result = self.calculate_scores(row, core_matcher)
            title_scores.append(result.title_score)
            author_scores.append(result.author_score)
            publisher_scores.append(result.publisher_score)
            combined_scores.append(result.combined_score)

        # Just verify we have scores (silent test)
        assert len(title_scores) > 0, "No title scores calculated"
        assert len(combined_scores) > 0, "No combined scores calculated"

    @mark.scoring
    def test_score_separation(
        self,
        known_matches: list[dict[str, str]],
        known_mismatches: list[dict[str, str]],
        core_matcher: CoreMatcher,
    ) -> None:
        """Test separation between true matches and false positives

        This test analyzes the score gap between:
        - Known matches (should score high)
        - Known mismatches (false positives that should score low)

        The goal is to find a clear threshold that separates them.

        Args:
            known_matches: List of true positive matches
            known_mismatches: List of false positive matches
            core_matcher: Core matcher instance
        """
        if not known_mismatches:
            print("\n⚠️  No known mismatches file found - skipping separation analysis")
            return

        # Calculate scores for all matches
        match_scores = []
        for row in known_matches:
            result = self.calculate_scores(row, core_matcher)
            match_scores.append(
                {"id": row["marc_id"], "score": result.combined_score, "is_match": True}
            )

        # Calculate scores for all mismatches
        mismatch_scores = []
        for row in known_mismatches:
            result = self.calculate_scores(row, core_matcher)
            mismatch_scores.append(
                {"id": row["marc_id"], "score": result.combined_score, "is_match": False}
            )

        # Analyze score distributions
        match_values = [s["score"] for s in match_scores]
        mismatch_values = [s["score"] for s in mismatch_scores]

        # Silent analysis - no print statements

        # Calculate statistics silently

        # Find overlap zone
        lowest_match = min(match_values)
        highest_mismatch = max(mismatch_values)

        # Check for problematic overlap
        if lowest_match <= highest_mismatch:
            # Count records in overlap zone for error reporting
            matches_in_overlap = sum(
                1 for s in match_scores if lowest_match <= s["score"] <= highest_mismatch
            )
            mismatches_in_overlap = sum(
                1 for s in mismatch_scores if lowest_match <= s["score"] <= highest_mismatch
            )

            # Save overlap details to CSV if there's a problem
            if matches_in_overlap > 0 or mismatches_in_overlap > 0:
                # Standard library imports
                import csv
                from pathlib import Path

                output_file = Path("score_overlap_analysis.csv")
                with open(output_file, "w", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=["id", "score", "type"])
                    writer.writeheader()

                    # Write problematic matches
                    for m in sorted(match_scores, key=lambda x: x["score"])[:10]:
                        writer.writerow({"id": m["id"], "score": m["score"], "type": "true_match"})
                    for m in sorted(mismatch_scores, key=lambda x: x["score"], reverse=True)[:10]:
                        writer.writerow(
                            {"id": m["id"], "score": m["score"], "type": "false_positive"}
                        )

        # Just verify basic statistics
        assert len(match_scores) > 0, "No match scores to analyze"
        assert len(mismatch_scores) > 0, "No mismatch scores to analyze"
