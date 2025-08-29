# tests/adapters/api/test_streaming_statistics.py

"""Test streaming component statistics collection.

Ensures that statistics are properly collected and aggregated in streaming mode.
"""

# Standard library imports
from unittest.mock import Mock
from unittest.mock import patch

# Local imports
from marc_pd_tool.adapters.api._streaming import StreamingComponent
from marc_pd_tool.application.models.analysis_results import AnalysisResults
from marc_pd_tool.application.models.batch_stats import BatchStats


def test_streaming_statistics_are_saved():
    """Test that streaming component saves statistics to results"""

    # Create a mock analyzer with results
    mock_analyzer = Mock()
    mock_analyzer.results = AnalysisResults()
    mock_analyzer.cache_dir = ".marcpd_cache"
    mock_analyzer.copyright_dir = "test_copyright"
    mock_analyzer.renewal_dir = "test_renewal"
    mock_analyzer.registration_index = None
    mock_analyzer.renewal_index = None
    mock_analyzer.generic_detector = None
    mock_analyzer.config = Mock()
    mock_analyzer.config.config = {}
    mock_analyzer._compute_config_hash = Mock(return_value="test_hash")

    # Create fake batch stats - simulating what would come from processing
    batch_stats = [
        BatchStats(
            batch_id=0,
            marc_count=1000,
            registration_matches_found=50,
            renewal_matches_found=25,
            us_records=800,
            non_us_records=200,
            skipped_no_year=100,
            records_with_errors=5,
        ),
        BatchStats(
            batch_id=1,
            marc_count=1000,
            registration_matches_found=60,
            renewal_matches_found=30,
            us_records=850,
            non_us_records=150,
            skipped_no_year=150,
            records_with_errors=3,
        ),
    ]

    # Mock the parallel processing to return our batch stats
    with patch("marc_pd_tool.adapters.api._streaming.Pool") as mock_pool_class:
        mock_pool = Mock()
        mock_pool_class.return_value.__enter__.return_value = mock_pool

        # Make imap_unordered return our batch stats with the expected format
        mock_results = [(0, "result_file_0", batch_stats[0]), (1, "result_file_1", batch_stats[1])]
        mock_pool.imap_unordered.return_value = iter(mock_results)

        # Call the streaming method
        batch_paths = ["batch1", "batch2"]  # Fake batch paths

        # Set up other mocks
        with patch("marc_pd_tool.adapters.api._streaming.mkdtemp") as mock_mkdtemp:
            mock_mkdtemp.return_value = "/tmp/test_results"
            with patch("marc_pd_tool.adapters.api._streaming.time") as mock_time:
                mock_time.return_value = 100
                with patch("marc_pd_tool.adapters.api._streaming.logger"):
                    with patch(
                        "marc_pd_tool.adapters.api._streaming.get_start_method"
                    ) as mock_start:
                        mock_start.return_value = "spawn"

                        # Mock options
                        mock_options = Mock()
                        mock_options.num_processes = 2

                        # Call the internal streaming method
                        StreamingComponent._process_streaming_parallel(
                            mock_analyzer,
                            batch_paths,
                            num_processes=2,
                            year_tolerance=1,
                            title_threshold=50,
                            author_threshold=50,
                            publisher_threshold=50,
                            early_exit_title=90,
                            early_exit_author=90,
                            early_exit_publisher=90,
                            score_everything_mode=False,
                            minimum_combined_score=50,
                            brute_force_missing_year=False,
                            min_year=None,
                            max_year=None,
                        )

    # Now check that statistics were properly set
    stats = mock_analyzer.results.statistics

    # Total records should be sum of both batches
    assert stats.total_records == 2000, f"Expected 2000 total records, got {stats.total_records}"

    # Registration matches should be summed
    assert (
        stats.registration_matches == 110
    ), f"Expected 110 reg matches, got {stats.registration_matches}"

    # Renewal matches should be summed
    assert stats.renewal_matches == 55, f"Expected 55 renewal matches, got {stats.renewal_matches}"

    # Other stats should also be summed
    assert stats.us_records == 1650
    assert stats.non_us_records == 350
    assert stats.skipped_no_year == 250

    # No matches should be calculated
    expected_no_matches = 2000 - (110 + 55)  # total - (reg + ren)
    assert stats.no_matches == expected_no_matches


def test_cli_receives_statistics():
    """Test that CLI properly receives statistics from analyzer"""

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
            "total_records": 190000,
            "registration_matches": 5000,
            "renewal_matches": 2500,
            "no_matches": 182500,
            "skipped_no_year": 23216,
            "us_records": 150000,
            "non_us_records": 40000,
            "unknown_country": 0,
        }

        mock_results.statistics.to_dict.return_value = mock_stats_dict
        mock_results.statistics.total_records = 190000
        mock_results.statistics.registration_matches = 5000
        mock_results.statistics.renewal_matches = 2500
        mock_results.statistics.skipped_no_year = 23216

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
                    kwargs = mock_log.call_args[1]

                    # THIS IS THE KEY TEST - ensuring 190k records show as 190k, not 0
                    assert (
                        kwargs["total_records"] == 190000
                    ), f"Expected 190000, got {kwargs['total_records']}"
                    assert kwargs["matched_records"] == 7500  # 5000 + 2500
                    assert kwargs["skipped_no_year"] == 23216


if __name__ == "__main__":
    test_streaming_statistics_are_saved()
    test_cli_receives_statistics()
    print("✓ All statistics tests passed!")
