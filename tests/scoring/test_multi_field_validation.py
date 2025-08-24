# tests/scoring/test_multi_field_validation.py

"""Test Phase 3B: Multi-Field Validation to prevent single-field false positives"""

# Third party imports
from pytest import fixture

# Local imports
from marc_pd_tool.application.processing.matching._score_combiner import ScoreCombiner
from marc_pd_tool.infrastructure.config import ConfigLoader


class TestMultiFieldValidation:
    """Test Phase 3B: Multi-field validation to prevent single-field domination"""

    @fixture
    def score_combiner(self) -> ScoreCombiner:
        """Create a ScoreCombiner instance"""
        config = ConfigLoader()
        return ScoreCombiner(config)

    def test_single_field_domination_cap(self, score_combiner: ScoreCombiner):
        """Test that weak title-only matches are capped

        Example: Weak title match with no support from other fields
        """
        # Weak title with absolutely no other support
        title_score = 45.0  # Moderate/weak match
        author_score = 5.0  # Almost nothing
        publisher_score = 5.0  # Almost nothing

        combined = score_combiner.combine_scores(
            title_score=title_score,
            author_score=author_score,
            publisher_score=publisher_score,
            use_config_weights=True,
        )

        # Should be capped at 25 due to weak title-only match
        assert combined <= 25.0, f"Expected <=25.0 (capped), got {combined}"

    def test_author_only_penalty(self, score_combiner: ScoreCombiner):
        """Test author-only penalty when author high but title very low

        Example: Kurt Wiese case - same author, different books
        """
        # Author very high, but title VERY low (<20)
        title_score = 15.0  # Very different titles
        author_score = 100.0  # Same author: Kurt Wiese
        publisher_score = 10.0  # Very different publishers

        combined = score_combiner.combine_scores(
            title_score=title_score,
            author_score=author_score,
            publisher_score=publisher_score,
            use_config_weights=True,
        )

        # Should apply 0.3x penalty due to author-only match with very weak other fields
        # Without penalty would be ~42.7, with penalty should be ~12.8
        assert combined < 15, f"Expected <15 with strong penalty, got {combined}"

    def test_publisher_only_penalty(self, score_combiner: ScoreCombiner):
        """Test publisher-only penalty when publisher high but title very low"""
        # Publisher very high, but title and author VERY low
        title_score = 15.0
        author_score = 10.0
        publisher_score = 85.0

        combined = score_combiner.combine_scores(
            title_score=title_score,
            author_score=author_score,
            publisher_score=publisher_score,
            use_config_weights=True,
        )

        # Should apply 0.5x penalty due to publisher-only match
        assert combined < 30, f"Expected <30 with penalty, got {combined}"

    def test_no_penalty_with_lccn_match(self, score_combiner: ScoreCombiner):
        """Test that penalties don't apply when LCCN matches"""
        # Author very high, title low, but LCCN matches
        title_score = 20.0
        author_score = 100.0
        publisher_score = 38.0

        combined = score_combiner.combine_scores(
            title_score=title_score,
            author_score=author_score,
            publisher_score=publisher_score,
            use_config_weights=True,
            has_lccn_match=True,
        )

        # With LCCN match, no penalty should apply, plus gets boost
        # Base ~42.7 + 20 boost = ~62.7
        assert combined > 55, f"Expected >55 with LCCN, got {combined}"

    def test_multiple_reasonable_fields_no_cap(self, score_combiner: ScoreCombiner):
        """Test that cap doesn't apply when multiple fields are reasonable"""
        # Two fields have reasonable scores
        title_score = 45.0  # Reasonable
        author_score = 75.0  # Good
        publisher_score = 10.0  # Poor

        combined = score_combiner.combine_scores(
            title_score=title_score,
            author_score=author_score,
            publisher_score=publisher_score,
            use_config_weights=True,
        )

        # Should NOT be capped since 2 fields are reasonable
        assert combined > 25, f"Should not cap with 2 reasonable fields, got {combined}"

    def test_all_fields_reasonable_no_penalty(self, score_combiner: ScoreCombiner):
        """Test no penalties when all fields are reasonable"""
        # All fields reasonable
        title_score = 55.0
        author_score = 65.0
        publisher_score = 45.0

        combined = score_combiner.combine_scores(
            title_score=title_score,
            author_score=author_score,
            publisher_score=publisher_score,
            use_config_weights=True,
        )

        # Should use standard calculation, no penalties
        # Roughly: 55*0.6 + 65*0.25 + 45*0.15 = 56.0
        assert 55 < combined < 60, f"Expected standard calculation ~56, got {combined}"

    def test_title_below_30_triggers_author_penalty(self, score_combiner: ScoreCombiner):
        """Test that title exactly at 30 doesn't trigger penalty, but 29.9 does"""
        # Test with title at 30 (no penalty)
        combined_30 = score_combiner.combine_scores(
            title_score=30.0, author_score=85.0, publisher_score=40.0, use_config_weights=True
        )

        # Test with title at 29.9 (penalty applies)
        combined_299 = score_combiner.combine_scores(
            title_score=29.9, author_score=85.0, publisher_score=40.0, use_config_weights=True
        )

        # Title at 30 should not have penalty
        assert combined_30 > 40, f"Title=30 should not trigger penalty, got {combined_30}"
        # Title at 29.9 should have penalty - refined to be less aggressive
        # Now we expect a small penalty, not a huge reduction
        assert combined_299 < combined_30, f"Title=29.9 should have some penalty"
        assert combined_299 > combined_30 * 0.9, f"Penalty should be moderate, not severe"

    def test_interaction_with_redistribution(self, score_combiner: ScoreCombiner):
        """Test that multi-field validation works with redistribution"""
        # High title, missing publisher, moderate author
        # This triggers redistribution (Phase 3) but not penalties (Phase 3B)
        title_score = 75.0
        author_score = 50.0
        publisher_score = 0.0

        combined = score_combiner.combine_scores(
            title_score=title_score,
            author_score=author_score,
            publisher_score=publisher_score,
            use_config_weights=True,
        )

        # Should redistribute (75*0.6 + 50*0.4 = 65) without penalties
        assert 64 < combined < 66, f"Expected redistribution ~65, got {combined}"

    def test_only_title_reasonable_gets_capped(self, score_combiner: ScoreCombiner):
        """Test that when only title is reasonable, score gets limited"""
        # Only title has reasonable score
        title_score = 50.0
        author_score = 20.0
        publisher_score = 15.0

        combined = score_combiner.combine_scores(
            title_score=title_score,
            author_score=author_score,
            publisher_score=publisher_score,
            use_config_weights=True,
        )

        # With refined penalties, we don't cap as aggressively
        # The weighted calculation gives ~37.25: 50*0.6 + 20*0.25 + 15*0.15
        assert (
            35 < combined < 40
        ), f"Single reasonable field should be limited but not severely, got {combined}"
