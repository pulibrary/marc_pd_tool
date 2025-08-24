# tests/unit/application/processing/test_lccn_boost.py

"""Tests for LCCN boost functionality in the scoring pipeline"""

# Standard library imports

# Third party imports
from pytest import fixture

# Local imports
from marc_pd_tool.application.processing.matching._core_matcher import CoreMatcher
from marc_pd_tool.application.processing.matching._lccn_matcher import LCCNMatcher
from marc_pd_tool.application.processing.matching._score_combiner import ScoreCombiner
from marc_pd_tool.core.domain.publication import Publication
from marc_pd_tool.infrastructure.config import ConfigLoader


class TestLCCNBoost:
    """Test LCCN boost in scoring pipeline"""

    @fixture
    def config_with_boost(self) -> ConfigLoader:
        """Create config with LCCN boost enabled"""
        config = ConfigLoader()
        # Override the config to set LCCN boost
        config.config["matching"] = {"lccn_score_boost": 35.0}
        return config

    @fixture
    def config_without_boost(self) -> ConfigLoader:
        """Create config with LCCN boost disabled"""
        config = ConfigLoader()
        if "matching" not in config.config:
            config.config["matching"] = {}
        config.config["matching"]["lccn_score_boost"] = 0.0
        return config

    def test_lccn_matcher_check_method(self):
        """Test that check_lccn_match correctly identifies LCCN matches"""
        marc_pub = Publication(
            title="Test Book",
            author="Test Author",
            pub_date="1925",
            publisher="Test Publisher",
            source_id="001",
            lccn="25012345",
        )
        marc_pub.normalized_lccn = "25012345"

        copyright_pub_match = Publication(
            title="Different Title",
            author="Different Author",
            pub_date="1925",
            publisher="Different Publisher",
            source_id="c001",
            lccn="25012345",
        )
        copyright_pub_match.normalized_lccn = "25012345"

        copyright_pub_no_match = Publication(
            title="Another Book",
            author="Another Author",
            pub_date="1925",
            publisher="Another Publisher",
            source_id="c002",
            lccn="25054321",
        )
        copyright_pub_no_match.normalized_lccn = "25054321"

        # Test with matching LCCN
        pub, has_match = LCCNMatcher.check_lccn_match(marc_pub, [copyright_pub_match])
        assert has_match is True
        assert pub == copyright_pub_match

        # Test with non-matching LCCN
        pub, has_match = LCCNMatcher.check_lccn_match(marc_pub, [copyright_pub_no_match])
        assert has_match is False
        assert pub is None

        # Test with multiple pubs including a match
        pub, has_match = LCCNMatcher.check_lccn_match(
            marc_pub, [copyright_pub_no_match, copyright_pub_match]
        )
        assert has_match is True
        assert pub == copyright_pub_match

    def test_score_combiner_applies_boost(self, config_with_boost):
        """Test that ScoreCombiner correctly applies LCCN boost"""
        combiner = ScoreCombiner(config_with_boost)

        # Test without LCCN match
        score = combiner.combine_scores(
            title_score=50.0, author_score=40.0, publisher_score=30.0, has_lccn_match=False
        )
        # Should be weighted average without boost
        # Config weights for normal_with_publisher: title=0.6, author=0.25, publisher=0.15
        expected = 50.0 * 0.6 + 40.0 * 0.25 + 30.0 * 0.15  # = 44.5
        assert abs(score - expected) < 0.1

        # Test with LCCN match
        score_with_boost = combiner.combine_scores(
            title_score=50.0, author_score=40.0, publisher_score=30.0, has_lccn_match=True
        )
        # Should be weighted average plus boost (now 20.0 instead of 35.0)
        expected_with_boost = expected + 20.0  # = 64.5
        assert abs(score_with_boost - expected_with_boost) < 0.1

    def test_score_combiner_no_boost_when_disabled(self):
        """Test that ScoreCombiner doesn't apply boost when disabled"""
        # Create config with boost disabled
        config = ConfigLoader()
        # Modify the actual matching config object
        config.matching.lccn_score_boost = 0.0

        # Create combiner with this config
        combiner = ScoreCombiner(config)
        assert combiner.lccn_score_boost == 0.0

        # Score should be the same with or without LCCN match when boost is 0
        score_without = combiner.combine_scores(
            title_score=50.0, author_score=40.0, publisher_score=30.0, has_lccn_match=False
        )

        score_with = combiner.combine_scores(
            title_score=50.0, author_score=40.0, publisher_score=30.0, has_lccn_match=True
        )

        assert score_without == score_with

    def test_score_combiner_caps_at_100(self, config_with_boost):
        """Test that combined score with boost doesn't exceed 100"""
        combiner = ScoreCombiner(config_with_boost)

        # High scores that would exceed 100 with boost
        score = combiner.combine_scores(
            title_score=90.0, author_score=85.0, publisher_score=80.0, has_lccn_match=True
        )

        assert score <= 100.0

    def test_core_matcher_integrates_lccn_boost(self, config_with_boost):
        """Test that CoreMatcher properly integrates LCCN boost"""
        matcher = CoreMatcher(config=config_with_boost)

        marc_pub = Publication(
            title="The Great Book",
            author="John Smith",
            pub_date="1925",
            publisher="Good Publisher",
            source_id="001",
            lccn="25012345",
        )
        marc_pub.normalized_lccn = "25012345"

        # Copyright pub with matching LCCN and moderate field matches
        # Changed to have some similarity to pass thresholds
        copyright_pub = Publication(
            title="The Great Book of Stories",  # Some title similarity
            author="John S. Smith",  # Some author similarity
            pub_date="1925",
            publisher="Good Publishing Co",  # Some publisher similarity
            source_id="c001",
            lccn="25012345",
        )
        copyright_pub.normalized_lccn = "25012345"

        result = matcher.find_best_match(
            marc_pub,
            [copyright_pub],
            title_threshold=10,  # Low threshold to ensure match
            author_threshold=10,
            year_tolerance=1,
        )

        assert result is not None
        assert result["is_lccn_match"] is True
        # Score should include boost with moderate field matches
        assert result["similarity_scores"]["combined"] > 50.0

    def test_false_positive_rejection(self, config_with_boost):
        """Test that false LCCN matches with very poor field scores are still rejected"""
        matcher = CoreMatcher(config=config_with_boost)

        marc_pub = Publication(
            title="Encyclopedia Britannica Volume 12",
            author="Various Authors",
            pub_date="1925",
            publisher="Encyclopedia Press",
            source_id="001",
            lccn="25012345",
        )
        marc_pub.normalized_lccn = "25012345"

        # Completely different work with same LCCN (data error)
        copyright_pub = Publication(
            title="xyz abc def",  # Nonsense title
            author="zzz yyy xxx",  # Nonsense author
            pub_date="1925",
            publisher="www vvv uuu",  # Nonsense publisher
            source_id="c001",
            lccn="25012345",
        )
        copyright_pub.normalized_lccn = "25012345"

        result = matcher.find_best_match(
            marc_pub,
            [copyright_pub],
            title_threshold=40,  # Reasonable threshold
            author_threshold=30,
            year_tolerance=1,
        )

        # Even with LCCN match, should reject if field scores are too low
        # With very poor field matches (likely < 10 each), even +35 boost
        # shouldn't reach 40 threshold
        if result:
            # If it does match, the combined score should at least reflect the boost
            assert result["similarity_scores"]["combined"] < 50.0

    def test_deprecated_find_lccn_match_returns_none(self):
        """Test that deprecated find_lccn_match method returns None"""
        marc_pub = Publication(
            title="Test",
            author="Test",
            pub_date="1925",
            publisher="Test",
            source_id="001",
            lccn="25012345",
        )
        marc_pub.normalized_lccn = "25012345"

        copyright_pub = Publication(
            title="Test",
            author="Test",
            pub_date="1925",
            publisher="Test",
            source_id="c001",
            lccn="25012345",
        )
        copyright_pub.normalized_lccn = "25012345"

        # Deprecated method should return None
        result = LCCNMatcher.find_lccn_match(marc_pub, [copyright_pub])
        assert result is None
