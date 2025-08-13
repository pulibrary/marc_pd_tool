# tests/test_processing/test_lccn_scoring.py

"""Tests for LCCN match scoring behavior"""

# Standard library imports

# Third party imports

# Local imports
from marc_pd_tool.application.processing.matching_engine import DataMatcher
from marc_pd_tool.core.domain.publication import Publication


class TestLCCNScoring:
    """Test LCCN match scoring in different modes"""

    def test_lccn_match_normal_mode_uses_negative_one(self):
        """Test that LCCN matches in normal mode use -1.0 for field scores"""
        matcher = DataMatcher()

        marc_pub = Publication(
            title="The Great Gatsby",
            author="F. Scott Fitzgerald",
            pub_date="1925",
            publisher="Scribner",
            source_id="001",
            lccn="25012345",
        )
        marc_pub.normalized_lccn = "25012345"

        copyright_pubs = [
            Publication(
                title="Completely Different Title",
                author="Unknown Author",
                pub_date="1925",
                publisher="Different Publisher",
                source_id="c001",
                lccn="25012345",
            )
        ]
        copyright_pubs[0].normalized_lccn = "25012345"

        # Normal mode match
        result = matcher.find_best_match(
            marc_pub,
            copyright_pubs,
            title_threshold=40,
            author_threshold=30,
            year_tolerance=1,
            publisher_threshold=60,
            early_exit_title=95,
            early_exit_author=90,
            generic_detector=None,
        )

        assert result is not None
        assert result["is_lccn_match"] == True
        # Field scores should be -1.0 to indicate "not checked"
        assert result["similarity_scores"]["title"] == -1.0
        assert result["similarity_scores"]["author"] == -1.0
        assert result["similarity_scores"]["publisher"] == -1.0
        # Combined score should still be 100 for LCCN match
        assert result["similarity_scores"]["combined"] == 100.0

    def test_lccn_match_score_everything_mode_calculates_real_scores(self):
        """Test that LCCN matches in score-everything mode calculate real scores"""
        matcher = DataMatcher()

        marc_pub = Publication(
            title="The Great Gatsby",
            author="F. Scott Fitzgerald",
            pub_date="1925",
            publisher="Scribner",
            source_id="001",
            lccn="25012345",
        )
        marc_pub.normalized_lccn = "25012345"

        copyright_pubs = [
            Publication(
                title="Great Gatsby",  # Similar but not exact
                author="F Scott Fitzgerald",  # Missing period
                pub_date="1925",
                publisher="Scribners",  # Extra 's'
                source_id="c001",
                lccn="25012345",
            )
        ]
        copyright_pubs[0].normalized_lccn = "25012345"

        # Score-everything mode
        result = matcher.find_best_match_ignore_thresholds(
            marc_pub, copyright_pubs, year_tolerance=1
        )

        assert result is not None
        assert result["is_lccn_match"] == True
        # Real scores should be calculated
        assert 0 < result["similarity_scores"]["title"] <= 100  # Not exact match
        assert 0 < result["similarity_scores"]["author"] <= 100  # Fuzzy match
        assert 0 < result["similarity_scores"]["publisher"] <= 100  # Fuzzy match
        assert 0 < result["similarity_scores"]["combined"] <= 100

    def test_lccn_match_with_exact_data_in_score_everything_mode(self):
        """Test LCCN match with exact data shows 100% scores in score-everything mode"""
        matcher = DataMatcher()

        marc_pub = Publication(
            title="The Great Gatsby",
            author="F. Scott Fitzgerald",
            pub_date="1925",
            publisher="Scribner",
            source_id="001",
            lccn="25012345",
        )
        marc_pub.normalized_lccn = "25012345"

        copyright_pubs = [
            Publication(
                title="The Great Gatsby",
                author="F. Scott Fitzgerald",
                pub_date="1925",
                publisher="Scribner",
                source_id="c001",
                lccn="25012345",
            )
        ]
        copyright_pubs[0].normalized_lccn = "25012345"

        # Score-everything mode
        result = matcher.find_best_match_ignore_thresholds(
            marc_pub, copyright_pubs, year_tolerance=1
        )

        assert result is not None
        assert result["is_lccn_match"] == True
        # Should get perfect scores for exact matches
        assert result["similarity_scores"]["title"] == 100.0
        assert result["similarity_scores"]["author"] > 80  # Fuzzy match can vary
        assert result["similarity_scores"]["publisher"] > 80  # Fuzzy match can vary
        assert result["similarity_scores"]["combined"] > 50  # Weighted combination

    def test_no_lccn_normal_behavior_unchanged(self):
        """Test that non-LCCN matches still work normally"""
        matcher = DataMatcher()

        marc_pub = Publication(
            title="The Great Gatsby",
            author="F. Scott Fitzgerald",
            pub_date="1925",
            source_id="001",
            # No LCCN
        )

        copyright_pubs = [
            Publication(
                title="The Great Gatsby",
                author="F. Scott Fitzgerald",
                pub_date="1925",
                source_id="c001",
                # No LCCN
            )
        ]

        result = matcher.find_best_match(
            marc_pub,
            copyright_pubs,
            title_threshold=40,
            author_threshold=30,
            year_tolerance=1,
            publisher_threshold=60,
            early_exit_title=95,
            early_exit_author=90,
            generic_detector=None,
        )

        assert result is not None
        assert result["is_lccn_match"] == False
        # Normal similarity scoring
        assert result["similarity_scores"]["title"] == 100.0
        assert result["similarity_scores"]["author"] > 80
        assert result["similarity_scores"]["publisher"] == 0.0  # No publisher data
        assert result["similarity_scores"]["combined"] > 0
