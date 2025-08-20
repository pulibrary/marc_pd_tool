# tests/regression/test_scoring_regression.py

#!/usr/bin/env python3
"""Regression test for scoring algorithm against known matches baseline.

This test is NOT run as part of the regular test suite. It should be run separately
to check for regressions or improvements in the scoring algorithm.

Usage:
    pdm run pytest tests/regression/test_scoring_regression.py -v

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
            lccn="",
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

    @mark.regression
    def test_scoring_matches_baseline(
        self, known_matches: list[dict[str, str]], core_matcher: CoreMatcher
    ) -> None:
        """Test that current scoring matches baseline scores

        This test will fail if the scoring algorithm changes in a way that
        affects the scores. This is intentional - any change should be reviewed
        to ensure it's an improvement, not a regression.

        Args:
            known_matches: List of known matches with baseline scores
            core_matcher: Core matcher instance
        """
        failures = []
        improvements = []

        for row in known_matches:
            marc_id = row["marc_id"]

            # Calculate current scores
            result = self.calculate_scores(row, core_matcher)

            # Get baseline scores
            baseline_title = float(row["baseline_title_score"])
            baseline_author = float(row["baseline_author_score"])
            baseline_publisher = float(row["baseline_publisher_score"])
            baseline_combined = float(row["baseline_combined_score"])

            # Check for exact matches (within small tolerance for floating point)
            tolerance = 0.01

            if abs(result.title_score - baseline_title) > tolerance:
                failures.append(f"{marc_id}: Title score {result.title_score} != {baseline_title}")

            if abs(result.author_score - baseline_author) > tolerance:
                failures.append(
                    f"{marc_id}: Author score {result.author_score} != {baseline_author}"
                )

            if abs(result.publisher_score - baseline_publisher) > tolerance:
                failures.append(
                    f"{marc_id}: Publisher score {result.publisher_score} != {baseline_publisher}"
                )

            if abs(result.combined_score - baseline_combined) > tolerance:
                diff = result.combined_score - baseline_combined
                if diff > 0:
                    improvements.append(
                        f"{marc_id}: Combined score improved {baseline_combined} -> {result.combined_score} (+{diff:.2f})"
                    )
                else:
                    failures.append(
                        f"{marc_id}: Combined score {result.combined_score} != {baseline_combined} ({diff:.2f})"
                    )

        # Print summary
        print(f"\n{'='*60}")
        print("SCORING REGRESSION TEST RESULTS")
        print(f"{'='*60}")
        print(f"Total records tested: {len(known_matches)}")

        if improvements:
            print(f"\n✅ Improvements found: {len(improvements)}")
            for imp in improvements[:10]:  # Show first 10
                print(f"  - {imp}")
            if len(improvements) > 10:
                print(f"  ... and {len(improvements) - 10} more")

        if failures:
            print(f"\n❌ Regressions found: {len(failures)}")
            for fail in failures[:10]:  # Show first 10
                print(f"  - {fail}")
            if len(failures) > 10:
                print(f"  ... and {len(failures) - 10} more")

            # Fail the test if there are regressions
            assert (
                False
            ), f"Found {len(failures)} scoring regressions. See output above for details."
        else:
            print("\n✅ All scores match baseline - no regressions detected!")

    @mark.regression
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
        percent_above = (above_threshold / total) * 100

        print(
            f"\nThreshold {threshold}: {above_threshold}/{total} ({percent_above:.1f}%) matches above threshold"
        )

    @mark.regression
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

        def calculate_stats(scores: list[float], name: str) -> None:
            """Calculate and print statistics for a set of scores"""
            if not scores:
                return

            sorted_scores = sorted(scores)
            n = len(sorted_scores)
            mean = sum(sorted_scores) / n
            median = (
                sorted_scores[n // 2]
                if n % 2
                else (sorted_scores[n // 2 - 1] + sorted_scores[n // 2]) / 2
            )
            min_score = min(sorted_scores)
            max_score = max(sorted_scores)
            q1 = sorted_scores[n // 4]
            q3 = sorted_scores[3 * n // 4]

            print(f"\n{name} Score Statistics:")
            print(f"  Mean: {mean:.1f}")
            print(f"  Median: {median:.1f}")
            print(f"  Min: {min_score:.1f}")
            print(f"  Max: {max_score:.1f}")
            print(f"  Q1: {q1:.1f}")
            print(f"  Q3: {q3:.1f}")

            # Distribution
            print(f"  Distribution:")
            for threshold in [0, 20, 40, 60, 80, 100]:
                count = sum(1 for s in sorted_scores if s >= threshold)
                percent = (count / n) * 100
                print(f"    >= {threshold}: {count} ({percent:.1f}%)")

        print(f"\n{'='*60}")
        print("FIELD SCORE STATISTICS")
        print(f"{'='*60}")

        calculate_stats(title_scores, "Title")
        calculate_stats(author_scores, "Author")
        calculate_stats(publisher_scores, "Publisher")
        calculate_stats(combined_scores, "Combined")
