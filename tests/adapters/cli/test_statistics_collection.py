# tests/adapters/cli/test_statistics_collection.py

"""Test that statistics are properly collected and reported through the CLI.

Ensures that statistics flow correctly from the analyzer to CLI output.
"""

# Standard library imports
from unittest.mock import Mock
from unittest.mock import patch

# Local imports
from marc_pd_tool.application.models.analysis_results import AnalysisResults


class TestStatisticsCollection:
    """Test that statistics are properly collected during processing"""

    def test_statistics_in_cli_output(self):
        """Test that statistics make it all the way to CLI output"""
        # This is a more end-to-end test
        # Standard library imports
        import sys

        # Local imports
        from marc_pd_tool.adapters.cli.main import main

        # Mock the entire analyzer
        with patch("marc_pd_tool.adapters.cli.main.MarcCopyrightAnalyzer") as mock_analyzer_class:
            mock_analyzer = Mock()
            mock_results = Mock()

            # Set up statistics that should flow through
            mock_stats_dict = {
                "total_records": 100,
                "registration_matches": 10,
                "renewal_matches": 5,
                "no_matches": 85,
                "skipped_no_year": 20,
                "unknown_country": 0,
                "us_records": 80,
                "non_us_records": 20,
            }

            mock_results.statistics.to_dict.return_value = mock_stats_dict
            mock_results.statistics.total_records = 100
            mock_results.statistics.registration_matches = 10
            mock_results.statistics.renewal_matches = 5
            mock_results.statistics.skipped_no_year = 20

            mock_analyzer.analyze_marc_file.return_value = mock_results
            mock_analyzer_class.return_value = mock_analyzer

            # Mock sys.argv
            test_args = [
                "marc-pd-tool",
                "--marcxml",
                "test.xml",
                "--copyright-dir",
                "test",
                "--renewal-dir",
                "test",
                "--output-filename",
                "test",
            ]

            with patch.object(sys, "argv", test_args):
                # Capture the log_run_summary call
                with patch("marc_pd_tool.adapters.cli.main.log_run_summary") as mock_log:
                    with patch("marc_pd_tool.adapters.cli.main.set_up_logging") as mock_setup:
                        mock_setup.return_value = (None, False)

                        main()

                        # Verify that log_run_summary received the correct stats
                        mock_log.assert_called_once()
                        call_kwargs = mock_log.call_args[1]

                        assert call_kwargs["total_records"] == 100
                        assert call_kwargs["matched_records"] == 15  # reg + renewal
                        assert call_kwargs["no_match_records"] == 85
                        assert call_kwargs["skipped_no_year"] == 20

    def test_analyzer_results_have_statistics(self):
        """Test that AnalysisResults properly initialize statistics"""
        results = AnalysisResults()

        # Check that statistics object exists and has expected attributes
        assert hasattr(results, "statistics")
        assert hasattr(results.statistics, "total_records")
        assert hasattr(results.statistics, "registration_matches")
        assert hasattr(results.statistics, "renewal_matches")
        assert hasattr(results.statistics, "no_matches")
        assert hasattr(results.statistics, "skipped_no_year")
        assert hasattr(results.statistics, "us_records")
        assert hasattr(results.statistics, "non_us_records")
        assert hasattr(results.statistics, "unknown_country")

        # Check initial values are 0
        assert results.statistics.total_records == 0
        assert results.statistics.registration_matches == 0
        assert results.statistics.renewal_matches == 0

        # Check that to_dict works
        stats_dict = results.statistics.to_dict()
        assert "total_records" in stats_dict
        assert "registration_matches" in stats_dict
        assert "renewal_matches" in stats_dict
