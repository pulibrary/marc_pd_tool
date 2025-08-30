# tests/adapters/api/test_stats_aggregation.py

"""Tests for copyright status aggregation from stats files"""

# Standard library imports
from pathlib import Path
from pickle import HIGHEST_PROTOCOL
from pickle import dump
from tempfile import TemporaryDirectory
from unittest.mock import patch

# Local imports
from marc_pd_tool.adapters.api._batch_processing import BatchProcessingComponent
from marc_pd_tool.application.models.analysis_results import AnalysisResults
from marc_pd_tool.application.models.analysis_results import AnalysisStatistics


def test_load_copyright_status_counts_from_stats_files():
    """Test that copyright status counts are properly loaded and aggregated from stats files"""

    # Create a simple mock object with the required attributes
    class MockAnalyzer:
        def __init__(self):
            self.results = AnalysisResults()
            self.results.statistics = AnalysisStatistics()

    mock_analyzer = MockAnalyzer()

    # Create temporary directory with test stats files
    with TemporaryDirectory() as temp_dir:
        # Create first batch stats file with copyright statuses
        stats1 = {
            "total_records": 100,
            "registration_matches": 40,
            "renewal_matches": 30,
            "us_renewed": 15,  # Copyright status
            "us_registered_not_renewed": 25,  # Copyright status
            "us_no_match": 60,  # Copyright status
            "foreign_no_match_fr": 5,  # Foreign copyright status
        }

        with open(Path(temp_dir) / "batch_00000_stats.pkl", "wb") as f:
            dump(stats1, f, protocol=HIGHEST_PROTOCOL)

        # Create second batch stats file with copyright statuses
        stats2 = {
            "total_records": 150,
            "registration_matches": 60,
            "renewal_matches": 45,
            "us_renewed": 20,  # Copyright status
            "us_registered_not_renewed": 40,  # Copyright status
            "us_no_match": 85,  # Copyright status
            "foreign_no_match_fr": 3,  # Foreign copyright status
            "foreign_no_match_de": 2,  # Another foreign status
        }

        with open(Path(temp_dir) / "batch_00001_stats.pkl", "wb") as f:
            dump(stats2, f, protocol=HIGHEST_PROTOCOL)

        # Call the method directly on the mock
        BatchProcessingComponent._load_copyright_status_counts_from_stats_files(
            mock_analyzer, temp_dir
        )

        # Verify the copyright status counts were aggregated correctly
        extra_fields = mock_analyzer.results.statistics.extra_fields

        # Check aggregated copyright status counts
        assert extra_fields["us_renewed"] == 35  # 15 + 20
        assert extra_fields["us_registered_not_renewed"] == 65  # 25 + 40
        assert extra_fields["us_no_match"] == 145  # 60 + 85
        assert extra_fields["foreign_no_match_fr"] == 8  # 5 + 3
        assert extra_fields["foreign_no_match_de"] == 2  # Only in second batch

        # Verify standard stats fields were NOT added to extra_fields
        assert "total_records" not in extra_fields
        assert "registration_matches" not in extra_fields
        assert "renewal_matches" not in extra_fields


def test_stats_to_dict_includes_extra_fields():
    """Test that to_dict() includes extra_fields in the output"""

    stats = AnalysisStatistics()

    # Set some regular fields
    stats.total_records = 1000
    stats.registration_matches = 400
    stats.renewal_matches = 300

    # Add some copyright status counts to extra_fields
    stats.extra_fields["us_renewed"] = 150
    stats.extra_fields["us_registered_not_renewed"] = 250
    stats.extra_fields["foreign_no_match_fr"] = 10

    # Convert to dict
    stats_dict = stats.to_dict()

    # Verify regular fields are present
    assert stats_dict["total_records"] == 1000
    assert stats_dict["registration_matches"] == 400
    assert stats_dict["renewal_matches"] == 300

    # Verify extra_fields are included
    assert stats_dict["us_renewed"] == 150
    assert stats_dict["us_registered_not_renewed"] == 250
    assert stats_dict["foreign_no_match_fr"] == 10

    # Verify extra_fields itself is not in the dict
    assert "extra_fields" not in stats_dict


def test_empty_stats_directory():
    """Test handling of empty stats directory"""

    class MockAnalyzer:
        def __init__(self):
            self.results = AnalysisResults()
            self.results.statistics = AnalysisStatistics()

    mock_analyzer = MockAnalyzer()

    with TemporaryDirectory() as temp_dir:
        # Directory exists but has no stats files
        BatchProcessingComponent._load_copyright_status_counts_from_stats_files(
            mock_analyzer, temp_dir
        )

        # Should not fail, just have empty extra_fields
        assert len(mock_analyzer.results.statistics.extra_fields) == 0


def test_corrupted_stats_file():
    """Test handling of corrupted stats files"""

    class MockAnalyzer:
        def __init__(self):
            self.results = AnalysisResults()
            self.results.statistics = AnalysisStatistics()

    mock_analyzer = MockAnalyzer()

    with TemporaryDirectory() as temp_dir:
        # Create a valid stats file
        stats1 = {"us_renewed": 10, "us_no_match": 20}
        with open(Path(temp_dir) / "batch_00000_stats.pkl", "wb") as f:
            dump(stats1, f, protocol=HIGHEST_PROTOCOL)

        # Create a corrupted file
        with open(Path(temp_dir) / "batch_00001_stats.pkl", "wb") as f:
            f.write(b"corrupted data that is not valid pickle")

        # Create another valid stats file
        stats2 = {"us_renewed": 15, "us_no_match": 25}
        with open(Path(temp_dir) / "batch_00002_stats.pkl", "wb") as f:
            dump(stats2, f, protocol=HIGHEST_PROTOCOL)

        # Should log warning but continue processing other files
        with patch("marc_pd_tool.adapters.api._batch_processing.logger") as mock_logger:
            BatchProcessingComponent._load_copyright_status_counts_from_stats_files(
                mock_analyzer, temp_dir
            )

            # Check that a warning was logged about the corrupted file
            assert mock_logger.warning.called

        # Should have aggregated the valid files
        extra_fields = mock_analyzer.results.statistics.extra_fields
        assert extra_fields["us_renewed"] == 25  # 10 + 15 (corrupted file skipped)
        assert extra_fields["us_no_match"] == 45  # 20 + 25
