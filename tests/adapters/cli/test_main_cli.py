# tests/adapters/cli/test_main_cli.py

"""Tests for the main CLI function covering uncovered lines"""

# Standard library imports
from unittest.mock import Mock
from unittest.mock import patch

# Local imports
from marc_pd_tool.cli import log_run_summary  # Use compatibility wrapper
from marc_pd_tool.cli import main


def create_mock_analyzer():
    """Create a mock analyzer with all required attributes"""
    mock_analyzer = Mock()
    mock_results = Mock()
    mock_results.statistics = {
        "total_records": 100,
        "registration_matches": 10,
        "renewal_matches": 5,
        "us_records": 100,
        "non_us_records": 0,
        "unknown_country": 0,
        "no_matches": 85,
        "pd_us_not_renewed": 25,
        "pd_us_not_renewed": 10,
        "in_copyright": 30,
        "research_us_status": 30,
        "research_us_only_pd": 5,
        "country_unknown": 0,
    }
    mock_analyzer.analyze_marc_file.return_value = mock_results
    return mock_analyzer


def create_mock_run_index_manager():
    """Create a mock run index manager"""
    mock = Mock()
    mock.add_run.return_value = None
    mock.update_run.return_value = None
    return mock


class TestMainCLI:
    """Test main() function to cover missing lines"""

    def test_main_logs_run_summary(self):
        """Test that main() calls log_run_summary (covers lines 362-390)"""
        test_args = [
            "compare.py",
            "--marcxml",
            "test.xml",
            "--copyright-dir",
            "/path/to/copyright",
            "--renewal-dir",
            "/path/to/renewal",
            "--output-filename",
            "results",
        ]

        with patch("sys.argv", test_args):
            with patch(
                "marc_pd_tool.adapters.cli.main.MarcCopyrightAnalyzer"
            ) as mock_analyzer_class:
                with patch("marc_pd_tool.adapters.cli.main.set_up_logging") as mock_logging:
                    with patch("marc_pd_tool.adapters.cli.main.log_run_summary") as mock_summary:
                        with patch(
                            "marc_pd_tool.adapters.cli.main.RunIndexManager"
                        ) as mock_run_index:
                            mock_analyzer_class.return_value = create_mock_analyzer()
                            mock_logging.return_value = ("/path/to/log.log", False)
                            mock_run_index.return_value = create_mock_run_index_manager()

                            main()

                            # Verify log_run_summary was called
                            mock_summary.assert_called_once()

    def test_main_with_min_year_logging(self):
        """Test that min_year is logged (covers lines 399-401)"""
        test_args = [
            "compare.py",
            "--marcxml",
            "test.xml",
            "--copyright-dir",
            "/path/to/copyright",
            "--renewal-dir",
            "/path/to/renewal",
            "--output-filename",
            "results",
            "--min-year",
            "1950",
        ]

        with patch("sys.argv", test_args):
            with patch(
                "marc_pd_tool.adapters.cli.main.MarcCopyrightAnalyzer"
            ) as mock_analyzer_class:
                with patch("marc_pd_tool.adapters.cli.main.set_up_logging") as mock_logging:
                    with patch("marc_pd_tool.adapters.cli.main.log_run_summary"):
                        with patch(
                            "marc_pd_tool.adapters.cli.main.RunIndexManager"
                        ) as mock_run_index:
                            with patch("marc_pd_tool.adapters.cli.main.logger") as mock_logger:
                                mock_analyzer_class.return_value = create_mock_analyzer()
                                mock_logging.return_value = (None, False)
                                mock_run_index.return_value = create_mock_run_index_manager()

                                main()

                                # Verify min_year was logged
                                calls = [str(call) for call in mock_logger.info.call_args_list]
                                assert any(
                                    "Using min_year filter: 1950" in str(call) for call in calls
                                )

    def test_main_full_execution_path(self):
        """Test full execution path through main() (covers lines 395-555)"""
        test_args = [
            "compare.py",
            "--marcxml",
            "test.xml",
            "--copyright-dir",
            "/path/to/copyright",
            "--renewal-dir",
            "/path/to/renewal",
            "--output-filename",
            "results",
            "--score-everything",
            "--max-workers",
            "4",
            "-vv",  # Use -vv for DEBUG level logging
        ]

        with patch("sys.argv", test_args):
            with patch(
                "marc_pd_tool.adapters.cli.main.MarcCopyrightAnalyzer"
            ) as mock_analyzer_class:
                with patch("marc_pd_tool.adapters.cli.main.set_up_logging") as mock_logging:
                    with patch("marc_pd_tool.adapters.cli.main.log_run_summary") as mock_summary:
                        with patch(
                            "marc_pd_tool.adapters.cli.main.RunIndexManager"
                        ) as mock_run_index:
                            with patch("marc_pd_tool.adapters.cli.main.logger") as mock_logger:
                                mock_analyzer = create_mock_analyzer()
                                mock_analyzer_class.return_value = mock_analyzer
                                mock_logging.return_value = ("/path/to/log.log", False)
                                mock_run_index_manager = create_mock_run_index_manager()
                                mock_run_index.return_value = mock_run_index_manager

                                main()

                                # Verify the full flow was executed
                                mock_analyzer_class.assert_called_once()
                                mock_analyzer.analyze_marc_file.assert_called_once()
                                mock_summary.assert_called_once()
                                mock_run_index_manager.add_run.assert_called_once()
                                mock_run_index_manager.update_run.assert_called_once()

                                # Verify logging calls
                                assert mock_logger.info.call_count >= 3

    def test_main_ground_truth_mode_execution(self):
        """Test ground truth mode execution (covers lines 469-499)"""
        test_args = [
            "compare.py",
            "--marcxml",
            "test.xml",
            "--output-filename",
            "results",
            "--ground-truth-mode",  # This is a flag, not expecting a file path
        ]

        with patch("sys.argv", test_args):
            with patch(
                "marc_pd_tool.adapters.cli.main.MarcCopyrightAnalyzer"
            ) as mock_analyzer_class:
                with patch("marc_pd_tool.adapters.cli.main.set_up_logging") as mock_logging:
                    with patch("marc_pd_tool.adapters.cli.main.RunIndexManager") as mock_run_index:
                        with patch("marc_pd_tool.adapters.cli.main.logger"):
                            mock_analyzer = create_mock_analyzer()
                            mock_analyzer.results = Mock()  # Add results attribute
                            mock_analyzer_class.return_value = mock_analyzer
                            mock_logging.return_value = (
                                None,
                                False,
                            )  # No log file, no progress bars
                            mock_run_index.return_value = create_mock_run_index_manager()

                            # Mock ground truth extraction at the class method level
                            with patch(
                                "marc_pd_tool.adapters.api._ground_truth.GroundTruthComponent.extract_ground_truth"
                            ) as mock_extract_gt:
                                # Mock ground truth stats
                                mock_stats = Mock()
                                mock_stats.marc_with_lccn = 100
                                mock_stats.marc_lccn_coverage = 50.0
                                mock_stats.registration_matches = 20
                                mock_stats.renewal_matches = 10
                                mock_stats.total_marc_records = 200

                                # Return some mock ground truth pairs
                                mock_pair = Mock()
                                mock_extract_gt.return_value = ([mock_pair], mock_stats)

                                # Mock that ground truth file exists
                                with patch("os.path.exists", return_value=True):
                                    main()

                                # Verify ground truth extraction was called
                                mock_extract_gt.assert_called_once()

                                # Verify results were stored correctly
                                assert mock_analyzer.results.ground_truth_pairs == [mock_pair]
                                assert mock_analyzer.results.ground_truth_stats == mock_stats


class TestLogRunSummaryFunction:
    """Test log_run_summary function directly (covers lines 362-390)"""

    def test_log_run_summary_complete_execution(self):
        """Test complete execution of log_run_summary"""
        results_stats = {
            "total_records": 1000,
            "registration_matches": 200,
            "renewal_matches": 150,
            "us_registered_not_renewed": 100,
            "us_pre_1929": 50,
            "us_renewed": 150,
            "foreign_no_match_gbr": 600,
            "foreign_renewed_fra": 50,
            "country_unknown_no_match": 50,
        }

        mock_args = Mock()
        mock_args.output_formats = ["csv", "json"]
        # Thresholds now come from config
        mock_args.min_year = None
        mock_args.max_year = None
        mock_args.us_only = False
        mock_args.output_file = "output.csv"

        with patch("marc_pd_tool.infrastructure.logging._setup.getLogger") as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            log_run_summary(10.5, results_stats, "output.csv", mock_args)

            # Verify logging was called (the actual logging happens in infrastructure layer)
            # The wrapper function calls _log_run_summary_new which does the actual logging
            # Test passes if no errors are raised

    def test_log_run_summary_handles_zero_duration(self):
        """Test log_run_summary with zero duration"""
        results_stats = {"total_records": 10, "registration_matches": 2, "renewal_matches": 1}

        mock_args = Mock()
        mock_args.output_formats = ["csv"]
        # Thresholds now come from config
        mock_args.min_year = None
        mock_args.max_year = None
        mock_args.us_only = False
        mock_args.output_file = "output.csv"

        with patch("marc_pd_tool.infrastructure.logging._setup.getLogger") as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            # Should not crash with zero duration
            log_run_summary(0.0, results_stats, "output.csv", mock_args)

            # Test passes if no errors are raised
