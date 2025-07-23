# tests/test_processing/test_author_threshold_fix.py

"""Test that author threshold is only applied when author data exists"""

# Standard library imports
from unittest.mock import Mock

# Third party imports
from pytest import fixture

# Local imports
from marc_pd_tool.data.publication import Publication
from marc_pd_tool.processing.matching_engine import DataMatcher


class TestAuthorThresholdFix:
    """Test author threshold logic for title-only matches"""

    @fixture
    def matching_engine(self):
        """Create a matching engine instance"""
        return DataMatcher()

    def test_title_only_match_not_rejected_by_author_threshold(self, matching_engine):
        """Test that title-only matches work when no author data exists"""
        # Create publications with no author data
        marc_pub = Publication(title="The Great Adventure")
        marc_pub.year = 1950
        marc_pub.language_code = "eng"

        copyright_pub = Publication(title="The Great Adventure")
        copyright_pub.year = 1950

        # Test with thresholds - should find match despite 0 author score
        match = matching_engine.find_best_match(
            marc_pub,
            [copyright_pub],
            title_threshold=30,
            author_threshold=25,  # Should not apply when no author data
            year_tolerance=1,
            publisher_threshold=30,
            early_exit_title=95,
            early_exit_author=90,
            generic_detector=None,
        )

        assert match is not None, "Title-only match should not be rejected by author threshold"
        assert match["similarity_scores"]["title"] == 100.0
        assert match["similarity_scores"]["author"] == 0.0

    def test_author_threshold_applied_when_author_data_exists(self, matching_engine):
        """Test that author threshold IS applied when author data exists"""
        # Create publications with author data
        marc_pub = Publication(title="The Great Adventure", author="John Smith")
        marc_pub.year = 1950
        marc_pub.language_code = "eng"

        copyright_pub = Publication(
            title="The Great Adventure", author="Jane Doe"
        )  # Different author
        copyright_pub.year = 1950

        # Mock the similarity calculator to return low author score
        mock_calc = Mock()
        mock_calc.calculate_title_similarity.return_value = 100.0
        mock_calc.calculate_author_similarity.return_value = 20.0  # Below threshold
        mock_calc.calculate_publisher_similarity.return_value = 0.0

        matching_engine.similarity_calculator = mock_calc

        # Test with thresholds - should NOT find match due to low author score
        match = matching_engine.find_best_match(
            marc_pub,
            [copyright_pub],
            title_threshold=30,
            author_threshold=25,  # Should apply and reject this match
            year_tolerance=1,
            publisher_threshold=30,
            early_exit_title=95,
            early_exit_author=90,
            generic_detector=None,
        )

        assert (
            match is None
        ), "Match should be rejected due to low author score when author data exists"

    def test_early_exit_with_no_author_data(self, matching_engine):
        """Test early exit works correctly when no author data exists"""
        # Create publications with no author data
        marc_pub = Publication(title="The Great Adventure")
        marc_pub.year = 1950
        marc_pub.language_code = "eng"

        # Create multiple potential matches
        copyright_pubs = [
            Publication(title="Different Book"),
            Publication(title="The Great Adventure"),  # Perfect match
            Publication(title="Another Book"),
        ]
        for pub in copyright_pubs:
            pub.year = 1950

        matches_evaluated = 0
        original_calc = matching_engine.similarity_calculator.calculate_title_similarity

        def counting_calc(title1, title2, lang):
            nonlocal matches_evaluated
            matches_evaluated += 1
            return original_calc(title1, title2, lang)

        matching_engine.similarity_calculator.calculate_title_similarity = counting_calc

        # Test with early exit thresholds
        match = matching_engine.find_best_match(
            marc_pub,
            copyright_pubs,
            title_threshold=30,
            author_threshold=25,
            year_tolerance=1,
            publisher_threshold=30,
            early_exit_title=95,  # Should trigger on perfect title match
            early_exit_author=90,
            generic_detector=None,
        )

        assert match is not None
        assert match["similarity_scores"]["title"] == 100.0
        # Should have exited early after finding perfect match
        assert matches_evaluated == 2, "Should have exited early after perfect title match"
