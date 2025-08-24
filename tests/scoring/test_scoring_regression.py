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
        # Track different types of changes
        combined_improvements = []
        combined_regressions = []
        field_changes = []
        unchanged = 0

        for row in known_matches:
            marc_id = row["marc_id"]

            # Calculate current scores
            result = self.calculate_scores(row, core_matcher)

            # Get baseline scores
            baseline_title = float(row["baseline_title_score"])
            baseline_author = float(row["baseline_author_score"])
            baseline_publisher = float(row["baseline_publisher_score"])
            baseline_combined = float(row["baseline_combined_score"])

            # Check for changes (within small tolerance for floating point)
            tolerance = 0.01

            # Track if any scores changed
            has_changes = False

            # Check individual field changes
            title_diff = result.title_score - baseline_title
            author_diff = result.author_score - baseline_author
            publisher_diff = result.publisher_score - baseline_publisher
            combined_diff = result.combined_score - baseline_combined

            # Record field-level changes
            if abs(title_diff) > tolerance:
                has_changes = True
                field_changes.append(
                    f"{marc_id}: Title {baseline_title:.1f} → {result.title_score:.1f} ({title_diff:+.1f})"
                )

            if abs(author_diff) > tolerance:
                has_changes = True
                field_changes.append(
                    f"{marc_id}: Author {baseline_author:.1f} → {result.author_score:.1f} ({author_diff:+.1f})"
                )

            if abs(publisher_diff) > tolerance:
                has_changes = True
                field_changes.append(
                    f"{marc_id}: Publisher {baseline_publisher:.1f} → {result.publisher_score:.1f} ({publisher_diff:+.1f})"
                )

            # Track combined score changes separately
            if abs(combined_diff) > tolerance:
                has_changes = True
                if combined_diff > 0:
                    combined_improvements.append(
                        f"{marc_id}: {baseline_combined:.1f} → {result.combined_score:.1f} (+{combined_diff:.2f})"
                    )
                else:
                    combined_regressions.append(
                        f"{marc_id}: {baseline_combined:.1f} → {result.combined_score:.1f} ({combined_diff:.2f})"
                    )

            if not has_changes:
                unchanged += 1

        # Print summary
        print(f"\n{'='*60}")
        print("SCORING REGRESSION TEST RESULTS")
        print(f"{'='*60}")
        print(f"Total records tested: {len(known_matches)}")
        print(f"Unchanged records: {unchanged}")
        print(f"Changed records: {len(known_matches) - unchanged}")

        # Show combined score changes
        if combined_improvements:
            print(f"\n✅ Combined Score Improvements: {len(combined_improvements)}")
            for imp in combined_improvements[:5]:  # Show first 5
                print(f"  - {imp}")
            if len(combined_improvements) > 5:
                print(f"  ... and {len(combined_improvements) - 5} more")

        if combined_regressions:
            print(f"\n⚠️  Combined Score Regressions: {len(combined_regressions)}")
            for reg in combined_regressions[:5]:  # Show first 5
                print(f"  - {reg}")
            if len(combined_regressions) > 5:
                print(f"  ... and {len(combined_regressions) - 5} more")

        # Show field changes summary
        if field_changes:
            # Count changes by field type
            title_changes = [c for c in field_changes if "Title" in c]
            author_changes = [c for c in field_changes if "Author" in c]
            publisher_changes = [c for c in field_changes if "Publisher" in c]

            print(f"\n📊 Field-Level Changes:")
            if title_changes:
                print(f"  Title: {len(title_changes)} changes")
            if author_changes:
                print(f"  Author: {len(author_changes)} changes")
            if publisher_changes:
                print(f"  Publisher: {len(publisher_changes)} changes")

            # Show a few examples
            print(f"\n  Examples of field changes:")
            for change in field_changes[:5]:
                print(f"    - {change}")
            if len(field_changes) > 5:
                print(f"    ... and {len(field_changes) - 5} more field changes")

        # Always show summary statistics if there are changes
        if combined_improvements or combined_regressions or field_changes:
            print(f"\n📈 Summary:")
            if combined_improvements:
                # Calculate improvement statistics
                improvements_values = []
                for imp in combined_improvements:
                    # Extract the improvement value from string like "(+2.25)"
                    # Standard library imports
                    import re

                    match = re.search(r"\(\+(\d+\.\d+)\)", imp)
                    if match:
                        improvements_values.append(float(match.group(1)))

                if improvements_values:
                    avg_improvement = sum(improvements_values) / len(improvements_values)
                    max_improvement = max(improvements_values)
                    min_improvement = min(improvements_values)
                    print(f"  Combined score improvements: {len(combined_improvements)} records")
                    print(f"    Average: +{avg_improvement:.2f} points")
                    print(f"    Range: +{min_improvement:.2f} to +{max_improvement:.2f} points")

            if combined_regressions:
                print(f"  Combined score regressions: {len(combined_regressions)} records")

        # Decision logic
        if combined_regressions:
            # Fail if there are combined score regressions
            print(f"\n❌ TEST FAILED: Found {len(combined_regressions)} combined score regressions")
            assert (
                False
            ), f"Found {len(combined_regressions)} combined score regressions. Review changes above."
        elif combined_improvements:
            print(f"\n✅ TEST PASSED: {len(combined_improvements)} improvements, no regressions!")
            print("The algorithm changes have improved matching accuracy.")
        elif field_changes:
            # Warning if fields changed but no combined improvement
            print(
                f"\n⚠️  TEST PASSED WITH WARNING: Field scores changed but no combined score improvements"
            )
            print("Review the field-level changes to ensure they are intentional.")
        else:
            print("\n✅ TEST PASSED: All scores match baseline exactly")
            print("No changes detected in the scoring algorithm.")

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
            f"Threshold {threshold}: {above_threshold}/{total} ({percent_above:.1f}%) matches above threshold"
        )

    @mark.regression
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

        # Report results
        if missing_column:
            print(
                f"\n⚠️ WARNING: {len(missing_column)} records missing score_without_lccn_boost column"
            )
            print("Run: pdm run python scripts/generate_baseline_scores.py to update")
        else:
            print("\n✅ All sampled records have score_without_lccn_boost column")

        if score_differences:
            print(f"\n📊 Found {len(score_differences)} records with LCCN boost:")
            avg_boost = sum(d["difference"] for d in score_differences) / len(score_differences)
            print(f"  Average boost: {avg_boost:.1f} points")

            # Show examples
            for item in score_differences[:3]:
                print(
                    f"  {item['id']}: {item['without_boost']:.1f} → {item['with_boost']:.1f} (+{item['difference']:.1f})"
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

    @mark.regression
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

        print(f"\n{'='*60}")
        print("SCORE SEPARATION ANALYSIS")
        print(f"{'='*60}")

        print(f"\n📊 Dataset Sizes:")
        print(f"  Known matches (true positives): {len(match_scores)}")
        print(f"  Known mismatches (false positives): {len(mismatch_scores)}")

        # True match statistics
        print(f"\n✅ TRUE MATCHES (should score high):")
        print(f"  Min score: {min(match_values):.2f}")
        print(f"  Max score: {max(match_values):.2f}")
        print(f"  Mean score: {sum(match_values)/len(match_values):.2f}")
        print(f"  Median score: {sorted(match_values)[len(match_values)//2]:.2f}")

        # False positive statistics
        print(f"\n❌ FALSE POSITIVES (should score low):")
        print(f"  Min score: {min(mismatch_values):.2f}")
        print(f"  Max score: {max(mismatch_values):.2f}")
        print(f"  Mean score: {sum(mismatch_values)/len(mismatch_values):.2f}")
        print(f"  Median score: {sorted(mismatch_values)[len(mismatch_values)//2]:.2f}")

        # Find overlap zone
        lowest_match = min(match_values)
        highest_mismatch = max(mismatch_values)

        if lowest_match > highest_mismatch:
            print(f"\n🎯 PERFECT SEPARATION!")
            print(f"  All true matches score >= {lowest_match:.2f}")
            print(f"  All false positives score <= {highest_mismatch:.2f}")
            print(f"  Safe threshold range: {highest_mismatch:.2f} - {lowest_match:.2f}")
        else:
            print(f"\n⚠️  OVERLAP ZONE: {lowest_match:.2f} - {highest_mismatch:.2f}")

            # Count records in overlap zone
            matches_in_overlap = sum(
                1 for s in match_scores if lowest_match <= s["score"] <= highest_mismatch
            )
            mismatches_in_overlap = sum(
                1 for s in mismatch_scores if lowest_match <= s["score"] <= highest_mismatch
            )

            print(f"  True matches in overlap: {matches_in_overlap}")
            print(f"  False positives in overlap: {mismatches_in_overlap}")

            # Find some example problem cases
            print(f"\n  Examples of lowest-scoring TRUE matches:")
            low_matches = sorted(match_scores, key=lambda x: x["score"])[:3]
            for m in low_matches:
                print(f"    - {m['id']}: {m['score']:.2f}")

            print(f"\n  Examples of highest-scoring FALSE positives:")
            high_mismatches = sorted(mismatch_scores, key=lambda x: x["score"], reverse=True)[:3]
            for m in high_mismatches:
                print(f"    - {m['id']}: {m['score']:.2f}")

        # Test various thresholds
        print(f"\n📈 THRESHOLD ANALYSIS:")
        thresholds = [20, 25, 30, 35, 40, 45, 50, 60, 70, 80, 90]

        for threshold in thresholds:
            true_positives = sum(1 for s in match_scores if s["score"] >= threshold)
            false_positives = sum(1 for s in mismatch_scores if s["score"] >= threshold)
            len(match_scores) - true_positives
            len(mismatch_scores) - false_positives

            precision = (
                true_positives / (true_positives + false_positives)
                if (true_positives + false_positives) > 0
                else 0
            )
            recall = true_positives / len(match_scores) if len(match_scores) > 0 else 0
            f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0

            print(f"\n  Threshold {threshold}:")
            print(
                f"    True Positives: {true_positives}/{len(match_scores)} ({true_positives/len(match_scores)*100:.1f}%)"
            )
            print(
                f"    False Positives: {false_positives}/{len(mismatch_scores)} ({false_positives/len(mismatch_scores)*100:.1f}%)"
            )
            print(f"    Precision: {precision:.3f}")
            print(f"    Recall: {recall:.3f}")
            print(f"    F1 Score: {f1:.3f}")
