# tests/unit/application/models/test_batch_stats.py

"""Tests for BatchStats model"""

# Third party imports

# Local imports
from marc_pd_tool.application.models.batch_stats import BatchStats
from marc_pd_tool.application.models.batch_stats import ScoreRange
from marc_pd_tool.application.models.batch_stats import ThresholdRecommendation


class TestScoreRange:
    """Test ScoreRange model"""

    def test_score_range_creation(self):
        """Test creating a ScoreRange"""
        score_range = ScoreRange(min=0.0, max=100.0, mean=50.0, median=45.0, std_dev=15.5)

        assert score_range.min == 0.0
        assert score_range.max == 100.0
        assert score_range.mean == 50.0
        assert score_range.median == 45.0
        assert score_range.std_dev == 15.5


class TestThresholdRecommendation:
    """Test ThresholdRecommendation model"""

    def test_threshold_recommendation_creation(self):
        """Test creating a ThresholdRecommendation"""
        recommendation = ThresholdRecommendation(title=85.0, author=75.0, combined=80.0)

        assert recommendation.title == 85.0
        assert recommendation.author == 75.0
        assert recommendation.combined == 80.0


class TestBatchStats:
    """Test BatchStats model"""

    def test_batch_stats_creation(self):
        """Test creating BatchStats with defaults"""
        stats = BatchStats(batch_id=1)

        assert stats.batch_id == 1
        assert stats.marc_count == 0
        assert stats.registration_matches_found == 0
        assert stats.renewal_matches_found == 0
        assert stats.processing_time == 0.0

    def test_batch_stats_with_values(self):
        """Test creating BatchStats with specific values"""
        stats = BatchStats(
            batch_id=5,
            marc_count=100,
            registration_matches_found=25,
            renewal_matches_found=10,
            processing_time=5.5,
            us_records=75,
            non_us_records=20,
            unknown_country_records=5,
        )

        assert stats.batch_id == 5
        assert stats.marc_count == 100
        assert stats.registration_matches_found == 25
        assert stats.renewal_matches_found == 10
        assert stats.processing_time == 5.5
        assert stats.us_records == 75
        assert stats.non_us_records == 20
        assert stats.unknown_country_records == 5

    def test_increment_existing_field(self):
        """Test incrementing an existing field"""
        stats = BatchStats(batch_id=1, marc_count=10)

        # Increment by default value (1)
        stats.increment("marc_count")
        assert stats.marc_count == 11

        # Increment by specific value
        stats.increment("marc_count", 5)
        assert stats.marc_count == 16

        # Test with other fields
        stats.increment("registration_matches_found", 3)
        assert stats.registration_matches_found == 3

    def test_increment_nonexistent_field(self):
        """Test incrementing a non-existent field (should do nothing)"""
        stats = BatchStats(batch_id=1)
        original_dict = stats.model_dump()

        # Try to increment non-existent field
        stats.increment("nonexistent_field", 10)

        # Should be unchanged
        assert stats.model_dump() == original_dict

    def test_to_dict(self):
        """Test converting BatchStats to dictionary"""
        stats = BatchStats(
            batch_id=2, marc_count=50, registration_matches_found=10, processing_time=2.5
        )

        result = stats.to_dict()

        assert isinstance(result, dict)
        assert result["batch_id"] == 2
        assert result["marc_count"] == 50
        assert result["registration_matches_found"] == 10
        assert result["processing_time"] == 2.5
        assert "renewal_matches_found" in result  # Should include all fields

    def test_all_fields_present(self):
        """Test that all expected fields are present"""
        stats = BatchStats(batch_id=1)
        stats_dict = stats.to_dict()

        expected_fields = [
            "batch_id",
            "marc_count",
            "registration_matches_found",
            "renewal_matches_found",
            "total_comparisons",
            "us_records",
            "non_us_records",
            "unknown_country_records",
            "processing_time",
            "skipped_no_year",
            "records_with_errors",
        ]

        for field in expected_fields:
            assert field in stats_dict, f"Missing field: {field}"
