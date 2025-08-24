# tests/scoring/test_missing_field_redistribution.py

"""Test missing field weight redistribution (Phase 3)"""

# Third party imports
from pytest import fixture
from pytest import mark

# Local imports
from marc_pd_tool.application.processing.matching._score_combiner import ScoreCombiner
from marc_pd_tool.infrastructure.config import ConfigLoader


class TestMissingFieldRedistribution:
    """Test Phase 3: Missing field weight redistribution"""

    @fixture
    def score_combiner(self) -> ScoreCombiner:
        """Create a ScoreCombiner instance"""
        config = ConfigLoader()
        return ScoreCombiner(config)

    def test_missing_author_with_good_title(self, score_combiner: ScoreCombiner):
        """Test redistribution when author missing but title matches well

        Example case: Commerce Clearing House appears as publisher in MARC
        but as author in copyright
        """
        # Title matches well, author missing, publisher present
        title_score = 84.0  # "United States master tax guide"
        author_score = 0.0  # Missing in one source
        publisher_score = 40.0  # "Commerce Clearing House"

        # With redistribution: title * 0.6 + publisher * 0.4 = 84*0.6 + 40*0.4 = 66.4
        combined = score_combiner.combine_scores(
            title_score=title_score,
            author_score=author_score,
            publisher_score=publisher_score,
            use_config_weights=True,
        )

        # Should be approximately 66.4 (redistributed)
        assert 65 < combined < 68, f"Expected ~66.4, got {combined}"

    def test_missing_publisher_with_good_title(self, score_combiner: ScoreCombiner):
        """Test redistribution when publisher missing but title matches well"""
        # Title matches well, publisher missing, author present
        title_score = 75.0
        author_score = 85.0
        publisher_score = 0.0

        # With redistribution: title * 0.6 + author * 0.4 = 75*0.6 + 85*0.4 = 79.0
        combined = score_combiner.combine_scores(
            title_score=title_score,
            author_score=author_score,
            publisher_score=publisher_score,
            use_config_weights=True,
        )

        # Should be approximately 79.0 (redistributed)
        assert 78 < combined < 80, f"Expected ~79.0, got {combined}"

    def test_no_redistribution_when_title_low(self, score_combiner: ScoreCombiner):
        """Test no redistribution when title score is below threshold"""
        # Title doesn't match well enough (< 70)
        title_score = 65.0
        author_score = 0.0
        publisher_score = 80.0

        # Should use standard calculation (not redistribution)
        combined = score_combiner.combine_scores(
            title_score=title_score,
            author_score=author_score,
            publisher_score=publisher_score,
            use_config_weights=True,
        )

        # With standard weights (0.5/0.3/0.2), normalized for missing author:
        # title gets 0.5/(0.5+0.2) = 0.714, publisher gets 0.2/(0.5+0.2) = 0.286
        # Expected: 65*0.714 + 80*0.286 = 46.4 + 22.9 = 69.3
        # But the actual calculation might differ based on config
        # The key is it should NOT be 65*0.6 + 80*0.4 = 71.0 (redistribution)
        assert combined < 70, f"Should not redistribute with low title, got {combined}"

    def test_no_redistribution_when_both_missing(self, score_combiner: ScoreCombiner):
        """Test no redistribution when BOTH author AND publisher missing"""
        # Only title present - too risky to redistribute
        title_score = 85.0
        author_score = 0.0
        publisher_score = 0.0

        # Should use standard calculation (title only)
        combined = score_combiner.combine_scores(
            title_score=title_score,
            author_score=author_score,
            publisher_score=publisher_score,
            use_config_weights=True,
        )

        # With only title, uses "normal_no_publisher" scenario
        # Title weight is 0.7, author weight is 0.3 (but author is 0)
        # After normalization with 0 author: title gets full weight
        # But there's also a generic title penalty factor of 0.8 if detected
        # The actual result depends on config, but should be less than redistribution
        assert combined < 65, f"Should use standard calculation, got {combined}"

    def test_no_redistribution_when_all_present(self, score_combiner: ScoreCombiner):
        """Test no redistribution when all fields present"""
        # All fields present - standard calculation
        title_score = 80.0
        author_score = 70.0
        publisher_score = 60.0

        # Should use standard calculation
        combined = score_combiner.combine_scores(
            title_score=title_score,
            author_score=author_score,
            publisher_score=publisher_score,
            use_config_weights=True,
        )

        # With config weights for "normal_with_publisher" (0.6/0.25/0.15):
        # 80*0.6 + 70*0.25 + 60*0.15 = 48 + 17.5 + 9 = 74.5
        assert 74 < combined < 75, f"Expected standard calculation ~74.5, got {combined}"

    def test_redistribution_with_lccn_boost(self, score_combiner: ScoreCombiner):
        """Test that redistribution works with LCCN boost"""
        # Missing author but with LCCN match
        title_score = 75.0
        author_score = 0.0
        publisher_score = 40.0

        # With redistribution: 75*0.6 + 40*0.4 = 61.0
        # Plus LCCN boost of 20: 61.0 + 20 = 81.0
        combined = score_combiner.combine_scores(
            title_score=title_score,
            author_score=author_score,
            publisher_score=publisher_score,
            use_config_weights=True,
            has_lccn_match=True,
        )

        # Should be approximately 81.0 (redistributed + LCCN boost)
        assert 80 < combined < 82, f"Expected ~81.0 with LCCN boost, got {combined}"

    @mark.parametrize(
        "title,author,publisher,expected_range,description",
        [
            (71.0, 0.0, 50.0, (62, 64), "Just above threshold"),
            (70.0, 0.0, 50.0, (62, 64), "Exactly at threshold"),
            (69.9, 0.0, 50.0, (49, 62), "Just below threshold"),
            (85.0, 0.0, 95.0, (89, 91), "High scores"),
            (70.0, 90.0, 0.0, (78, 80), "Missing publisher"),
        ],
    )
    def test_redistribution_threshold_boundaries(
        self,
        score_combiner: ScoreCombiner,
        title: float,
        author: float,
        publisher: float,
        expected_range: tuple[float, float],
        description: str,
    ):
        """Test redistribution behavior at threshold boundaries"""
        combined = score_combiner.combine_scores(
            title_score=title,
            author_score=author,
            publisher_score=publisher,
            use_config_weights=True,
        )

        assert (
            expected_range[0] <= combined <= expected_range[1]
        ), f"{description}: Expected {expected_range}, got {combined}"
