# tests/test_processing/test_author_threshold_fix.py

"""Test that author threshold is only applied when author data exists"""

# Standard library imports
from unittest.mock import Mock

# Third party imports
from pytest import fixture

# Local imports
from marc_pd_tool.application.processing.matching_engine import DataMatcher
from marc_pd_tool.core.domain.publication import Publication


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
        def mock_calculate_similarity(text1, text2, field_type, language):
            if field_type == "title":
                return 100.0
            elif field_type == "author":
                return 20.0  # Below threshold
            else:
                return 0.0

        mock_calc = Mock()
        mock_calc.calculate_similarity = Mock(side_effect=mock_calculate_similarity)
        # Need to mock the core_matcher's similarity_calculator
        matching_engine.core_matcher.similarity_calculator = mock_calc

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
        # Access the core_matcher's similarity calculator
        original_calc = matching_engine.core_matcher.similarity_calculator.calculate_similarity

        def counting_calc(text1, text2, field_type, language):
            nonlocal matches_evaluated
            if field_type == "title":
                matches_evaluated += 1
            return original_calc(text1, text2, field_type, language)

        matching_engine.core_matcher.similarity_calculator.calculate_similarity = counting_calc

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
