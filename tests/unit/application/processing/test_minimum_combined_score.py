# tests/unit/application/processing/test_minimum_combined_score.py

"""Test minimum combined score threshold in score-everything mode"""

# Standard library imports
from unittest.mock import Mock

# Third party imports
from pytest import fixture

# Local imports
from marc_pd_tool.application.processing.matching_engine import DataMatcher
from marc_pd_tool.core.domain.publication import Publication


class TestMinimumCombinedScore:
    """Test minimum combined score threshold functionality"""

    @fixture
    def matching_engine(self):
        """Create a matching engine instance"""
        return DataMatcher()

    def test_minimum_combined_score_rejects_low_matches(self, matching_engine):
        """Test that matches below minimum combined score are rejected"""
        # Create publications
        marc_pub = Publication(title="Test Book")
        marc_pub.year = 1950
        marc_pub.language_code = "eng"

        # Create a poor match
        copyright_pub = Publication(title="Different Book", author="Different Author")
        copyright_pub.year = 1950

        # Mock the similarity calculator to return low scores
        mock_calc = Mock()
        mock_calc.calculate_title_similarity.return_value = 20.0  # Low title score
        mock_calc.calculate_author_similarity.return_value = 20.0  # Low author score
        mock_calc.calculate_publisher_similarity.return_value = 0.0

        matching_engine.similarity_calculator = mock_calc

        # Test with minimum combined score of 40
        match = matching_engine.find_best_match_ignore_thresholds(
            marc_pub, [copyright_pub], year_tolerance=1, minimum_combined_score=40
        )

        # Should return None because combined score will be ~20 (below 40)
        assert match is None, "Match with combined score below minimum should be rejected"

    def test_minimum_combined_score_accepts_good_matches(self, matching_engine):
        """Test that matches above minimum combined score are accepted"""
        # Create publications with good similarity
        marc_pub = Publication(title="The Great Adventure")
        marc_pub.year = 1950
        marc_pub.language_code = "eng"

        copyright_pub = Publication(title="The Great Adventure")
        copyright_pub.year = 1950

        # Test with minimum combined score of 40
        match = matching_engine.find_best_match_ignore_thresholds(
            marc_pub, [copyright_pub], year_tolerance=1, minimum_combined_score=40
        )

        # Should return match because title similarity will be 100%
        assert match is not None, "Match with combined score above minimum should be accepted"
        assert match["similarity_scores"]["title"] == 100.0
        assert match["similarity_scores"]["combined"] >= 40.0

    def test_no_minimum_score_returns_any_match(self, matching_engine):
        """Test that without minimum score, any match is returned"""
        # Create publications with poor similarity
        marc_pub = Publication(title="Test Book")
        marc_pub.year = 1950
        marc_pub.language_code = "eng"

        copyright_pub = Publication(title="Completely Different Title")
        copyright_pub.year = 1950

        # Test without minimum combined score
        match = matching_engine.find_best_match_ignore_thresholds(
            marc_pub, [copyright_pub], year_tolerance=1, minimum_combined_score=None  # No minimum
        )

        # Should return match even with low score
        assert match is not None, "Without minimum score, any match should be returned"

    def test_best_match_selected_before_minimum_check(self, matching_engine):
        """Test that best match is selected before applying minimum threshold"""
        # Create publications
        marc_pub = Publication(title="Test Book")
        marc_pub.year = 1950
        marc_pub.language_code = "eng"

        # Create multiple matches with varying scores
        poor_match = Publication(title="Different Book")
        poor_match.year = 1950

        good_match = Publication(title="Test Book")  # Exact match
        good_match.year = 1950

        # Test with minimum combined score of 40
        match = matching_engine.find_best_match_ignore_thresholds(
            marc_pub, [poor_match, good_match], year_tolerance=1, minimum_combined_score=40
        )

        # Should return the good match (100% title score)
        assert match is not None
        assert match["similarity_scores"]["title"] == 100.0
        # Title preserves original case
        assert match["copyright_record"]["title"] == "Test Book"
