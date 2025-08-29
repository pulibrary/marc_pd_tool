# tests/scoring/test_non_lccn_performance.py

"""Test matching performance without LCCN boost to simulate non-LCCN records.

This test uses the same ground truth dataset but disables LCCN scoring to understand
how the algorithm would perform on records without LCCNs.
"""

# Standard library imports
from csv import DictReader
from pathlib import Path

# Third party imports
from pytest import fixture
from pytest import mark

# Local imports
from marc_pd_tool.application.processing.matching._core_matcher import CoreMatcher
from marc_pd_tool.core.domain.publication import Publication
from marc_pd_tool.infrastructure.config import ConfigLoader


class TestNonLCCNPerformance:
    """Test matching performance without LCCN boost"""

    @fixture(scope="class")
    def matcher_no_lccn(self) -> CoreMatcher:
        """Create matcher with LCCN boost disabled"""
        config = ConfigLoader()
        # Disable LCCN boost completely
        config.matching.lccn_score_boost = 0.0
        return CoreMatcher(config)

    @fixture(scope="class")
    def matcher_with_lccn(self) -> CoreMatcher:
        """Create matcher with default LCCN boost"""
        config = ConfigLoader()
        # Use default boost (35.0)
        return CoreMatcher(config)

    @fixture(scope="class")
    def known_matches(self) -> list[dict[str, str]]:
        """Load known matches"""
        path = Path("tests/fixtures/known_matches_with_baselines.csv")
        with open(path, "r") as f:
            reader = DictReader(f)
            return list(reader)

    @fixture(scope="class")
    def known_mismatches(self) -> list[dict[str, str]]:
        """Load known mismatches (false positives)"""
        path = Path("tests/fixtures/known_mismatches_with_baselines.csv")
        if not path.exists():
            return []
        with open(path, "r") as f:
            reader = DictReader(f)
            return list(reader)

    def calculate_scores(
        self, row: dict[str, str], matcher: CoreMatcher, disable_lccn: bool = False
    ) -> dict[str, float]:
        """Calculate scores for a match pair"""
        # Create publications
        marc_pub = Publication(
            title=row["marc_title_original"],
            author=row["marc_author_original"],
            main_author=row["marc_main_author_original"],
            publisher=row["marc_publisher_original"],
            year=int(row["marc_year"]) if row["marc_year"] else None,
            lccn=row.get("marc_lccn") if not disable_lccn else "",  # Clear LCCN if disabled
            source_id=row["marc_id"],
        )

        # Normalize LCCN only if not disabled
        if not disable_lccn and marc_pub.lccn:
            marc_pub.normalized_lccn = row.get("marc_lccn_normalized", "")

        copyright_pub = Publication(
            title=row["match_title"],
            author=row["match_author"],
            publisher=row["match_publisher"],
            year=int(row["match_year"]) if row["match_year"] else None,
            # For testing LCCN impact, copyright record needs same LCCN when enabled
            lccn=row.get("marc_lccn") if not disable_lccn else "",
            source_id=row.get("match_source_id", ""),
        )

        # Normalize LCCN for copyright record too if not disabled
        if not disable_lccn and copyright_pub.lccn:
            copyright_pub.normalized_lccn = row.get("marc_lccn_normalized", "")

        # Get match result
        result = matcher.find_best_match_ignore_thresholds(
            marc_pub, [copyright_pub], year_tolerance=100, minimum_combined_score=0
        )

        if result:
            scores = result["similarity_scores"]
            return {
                "title": scores["title"],
                "author": scores["author"],
                "publisher": scores["publisher"],
                "combined": scores["combined"],
            }
        return {"title": 0, "author": 0, "publisher": 0, "combined": 0}

    @mark.scoring
    def test_score_comparison_with_without_lccn(
        self,
        known_matches: list[dict[str, str]],
        matcher_no_lccn: CoreMatcher,
        matcher_with_lccn: CoreMatcher,
    ) -> None:
        """Compare scores with and without LCCN boost"""

        score_differences = []

        # Sample first 100 for detailed analysis
        for row in known_matches[:100]:
            # Calculate with LCCN
            scores_with = self.calculate_scores(row, matcher_with_lccn, disable_lccn=False)

            # Calculate without LCCN (simulating no LCCN available)
            scores_without = self.calculate_scores(row, matcher_no_lccn, disable_lccn=True)

            diff = scores_with["combined"] - scores_without["combined"]
            if diff > 0:  # Only records that had LCCN boost
                score_differences.append(
                    {
                        "id": row["marc_id"],
                        "with_lccn": scores_with["combined"],
                        "without_lccn": scores_without["combined"],
                        "difference": diff,
                        "title": row["marc_title_original"][:50],
                    }
                )

        # Just verify we have some differences
        assert len(score_differences) > 0, "No LCCN boost differences found"

    @mark.scoring
    def test_threshold_analysis_without_lccn(
        self,
        known_matches: list[dict[str, str]],
        known_mismatches: list[dict[str, str]],
        matcher_no_lccn: CoreMatcher,
    ) -> None:
        """Analyze performance at various thresholds without LCCN"""

        # Use the pre-calculated score_without_lccn_boost if available
        # Otherwise calculate scores for all matches WITHOUT LCCN
        match_scores = []
        for row in known_matches:
            if "score_without_lccn_boost" in row and row["score_without_lccn_boost"]:
                # Use pre-calculated score from CSV
                match_scores.append(float(row["score_without_lccn_boost"]))
            else:
                # Calculate it (backwards compatibility)
                scores = self.calculate_scores(row, matcher_no_lccn, disable_lccn=True)
                match_scores.append(scores["combined"])

        # Calculate scores for mismatches WITHOUT LCCN
        mismatch_scores = []
        for row in known_mismatches:
            if "score_without_lccn_boost" in row and row["score_without_lccn_boost"]:
                # Use pre-calculated score from CSV
                mismatch_scores.append(float(row["score_without_lccn_boost"]))
            else:
                # Calculate it (backwards compatibility)
                scores = self.calculate_scores(row, matcher_no_lccn, disable_lccn=True)
                mismatch_scores.append(scores["combined"])

        # Just verify we have scores
        assert len(match_scores) > 0, "No match scores calculated"
        assert len(mismatch_scores) > 0, "No mismatch scores calculated"

        # Verify reasonable score separation
        median_match = sorted(match_scores)[len(match_scores) // 2]
        median_mismatch = (
            sorted(mismatch_scores)[len(mismatch_scores) // 2] if mismatch_scores else 0
        )
        assert median_match > median_mismatch, "Match scores should be higher than mismatch scores"

    @mark.scoring
    def test_records_failing_without_lccn(
        self, known_matches: list[dict[str, str]], matcher_no_lccn: CoreMatcher
    ) -> None:
        """Identify records that would fail to match without LCCN boost"""

        failing_records = []
        threshold = 40  # A reasonable threshold

        # Test sample of records
        for row in known_matches[:500]:
            scores = self.calculate_scores(row, matcher_no_lccn, disable_lccn=True)

            if scores["combined"] < threshold:
                failing_records.append(
                    {
                        "id": row["marc_id"],
                        "score": scores["combined"],
                        "title": row["marc_title_original"][:60],
                        "author": row["marc_author_original"][:40],
                        "title_score": scores["title"],
                        "author_score": scores["author"],
                    }
                )

        # Just verify the failure rate is reasonable
        failure_rate = len(failing_records) / 500
        # We expect some failures without LCCN, but not too many
        assert failure_rate < 0.5, f"Too many failures without LCCN: {failure_rate*100:.1f}%"
