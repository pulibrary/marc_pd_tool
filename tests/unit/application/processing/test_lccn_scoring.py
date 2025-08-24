# tests/unit/application/processing/test_lccn_scoring.py

"""Tests for LCCN match scoring behavior"""

# Standard library imports

# Third party imports
from pytest import fixture

# Local imports
from marc_pd_tool.application.processing.matching_engine import DataMatcher
from marc_pd_tool.core.domain.publication import Publication
from marc_pd_tool.infrastructure.config import ConfigLoader


class TestLCCNScoring:
    """Test LCCN match scoring in different modes"""

    @fixture
    def matcher_with_boost(self):
        """Create matcher with LCCN boost enabled"""
        config = ConfigLoader()
        config.config["matching"] = {"lccn_score_boost": 35.0}
        return DataMatcher(config=config)

    def test_lccn_match_now_calculates_field_scores(self, matcher_with_boost):
        """Test that LCCN matches now calculate real field scores instead of -1.0"""
        marc_pub = Publication(
            title="The Great Gatsby",
            author="F. Scott Fitzgerald",
            pub_date="1925",
            publisher="Scribner",
            source_id="001",
            lccn="25012345",
        )
        marc_pub.normalized_lccn = "25012345"

        # Use moderate field matches that would qualify for conditional LCCN boost
        copyright_pubs = [
            Publication(
                title="Great Gatsby",  # Similar but not exact (will score ~70-80)
                author="Fitzgerald",  # Partial match (will score ~60-70)
                pub_date="1925",
                publisher="Scribners",  # Close match (will score ~80+)
                source_id="c001",
                lccn="25012345",
            )
        ]
        copyright_pubs[0].normalized_lccn = "25012345"

        # Normal mode match
        result = matcher_with_boost.find_best_match(
            marc_pub,
            copyright_pubs,
            title_threshold=10,  # Low threshold to ensure match
            author_threshold=10,
            year_tolerance=1,
            publisher_threshold=10,
            early_exit_title=95,
            early_exit_author=90,
            generic_detector=None,
        )

        assert result is not None
        assert result["is_lccn_match"] is True
        # Field scores should now be calculated (not -1.0)
        assert result["similarity_scores"]["title"] > 0
        assert result["similarity_scores"]["title"] <= 100
        assert result["similarity_scores"]["author"] >= 0
        assert result["similarity_scores"]["author"] <= 100
        assert result["similarity_scores"]["publisher"] >= 0
        assert result["similarity_scores"]["publisher"] <= 100
        # Combined score should include LCCN boost
        assert result["similarity_scores"]["combined"] > 30.0

    def test_lccn_match_score_everything_mode_still_works(self, matcher_with_boost):
        """Test that score-everything mode still calculates scores properly"""
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
        result = matcher_with_boost.find_best_match_ignore_thresholds(
            marc_pub, copyright_pubs, year_tolerance=1
        )

        assert result is not None
        assert result["is_lccn_match"] is True
        # Real scores should be calculated
        assert 0 < result["similarity_scores"]["title"] <= 100
        assert 0 < result["similarity_scores"]["author"] <= 100
        assert 0 < result["similarity_scores"]["publisher"] <= 100
        # Combined should be high due to good field matches + LCCN boost
        assert result["similarity_scores"]["combined"] > 80.0

    def test_lccn_false_positive_can_be_rejected(self, matcher_with_boost):
        """Test that LCCN matches with very poor field scores can be rejected"""
        marc_pub = Publication(
            title="Encyclopedia Britannica",
            author="Editorial Board",
            pub_date="1925",
            publisher="Britannica Press",
            source_id="001",
            lccn="25012345",
        )
        marc_pub.normalized_lccn = "25012345"

        # Completely different work with same LCCN (data error)
        copyright_pubs = [
            Publication(
                title="zzz xxx yyy",  # Nonsense that won't match
                author="aaa bbb ccc",
                pub_date="1925",
                publisher="ddd eee fff",
                source_id="c001",
                lccn="25012345",
            )
        ]
        copyright_pubs[0].normalized_lccn = "25012345"

        # With reasonable thresholds, should reject despite LCCN
        result = matcher_with_boost.find_best_match(
            marc_pub,
            copyright_pubs,
            title_threshold=50,  # Reasonable threshold
            author_threshold=40,
            year_tolerance=1,
            publisher_threshold=40,
            early_exit_title=95,
            early_exit_author=90,
            generic_detector=None,
        )

        # Should be None because field scores are too low even with boost
        assert result is None

    def test_good_lccn_match_still_scores_high(self, matcher_with_boost):
        """Test that good LCCN matches with good field scores still score very high"""
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
                title="The Great Gatsby",  # Exact match
                author="F. Scott Fitzgerald",  # Exact match
                pub_date="1925",
                publisher="Scribner",  # Exact match
                source_id="c001",
                lccn="25012345",
            )
        ]
        copyright_pubs[0].normalized_lccn = "25012345"

        result = matcher_with_boost.find_best_match(
            marc_pub,
            copyright_pubs,
            title_threshold=40,
            author_threshold=30,
            year_tolerance=1,
            publisher_threshold=40,
            early_exit_title=95,
            early_exit_author=90,
            generic_detector=None,
        )

        assert result is not None
        assert result["is_lccn_match"] is True
        # Field scores should be near perfect
        assert result["similarity_scores"]["title"] >= 95.0
        assert result["similarity_scores"]["author"] >= 95.0
        assert result["similarity_scores"]["publisher"] >= 95.0
        # Combined should be at 100 (perfect match + boost, capped)
        assert result["similarity_scores"]["combined"] == 100.0
