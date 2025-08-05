# tests/test_cli/test_main_cli.py

"""Tests for the main CLI function covering uncovered lines"""

# Standard library imports
from unittest.mock import Mock
from unittest.mock import patch

# Local imports
from marc_pd_tool.cli import log_run_summary
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
            with patch("marc_pd_tool.cli.MarcCopyrightAnalyzer") as mock_analyzer_class:
                with patch("marc_pd_tool.cli.set_up_logging") as mock_logging:
                    with patch("marc_pd_tool.cli.log_run_summary") as mock_summary:
                        with patch("marc_pd_tool.cli.RunIndexManager") as mock_run_index:
                            mock_analyzer_class.return_value = create_mock_analyzer()
                            mock_logging.return_value = "/path/to/log.log"
                            mock_run_index.return_value = create_mock_run_index_manager()

                            main()

                            # Verify log_run_summary was called
                            mock_summary.assert_called_once()
                            # Check it was called with correct number of args
                            assert len(mock_summary.call_args[0]) == 4

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
            with patch("marc_pd_tool.cli.MarcCopyrightAnalyzer") as mock_analyzer_class:
                with patch("marc_pd_tool.cli.set_up_logging") as mock_logging:
                    with patch("marc_pd_tool.cli.log_run_summary"):
                        with patch("marc_pd_tool.cli.RunIndexManager") as mock_run_index:
                            with patch("marc_pd_tool.cli.logger") as mock_logger:
                                mock_analyzer_class.return_value = create_mock_analyzer()
                                mock_logging.return_value = None
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
            "--score-everything-mode",
            "--max-workers",
            "4",
            "--debug",
        ]

        with patch("sys.argv", test_args):
            with patch("marc_pd_tool.cli.MarcCopyrightAnalyzer") as mock_analyzer_class:
                with patch("marc_pd_tool.cli.set_up_logging") as mock_logging:
                    with patch("marc_pd_tool.cli.log_run_summary") as mock_summary:
                        with patch("marc_pd_tool.cli.RunIndexManager") as mock_run_index:
                            with patch("marc_pd_tool.cli.logger") as mock_logger:
                                mock_analyzer = create_mock_analyzer()
                                mock_analyzer_class.return_value = mock_analyzer
                                mock_logging.return_value = "/path/to/log.log"
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
                                assert mock_logger.info.call_count >= 5

    def test_main_ground_truth_mode_execution(self):
        """Test ground truth mode execution (covers lines 469-499)"""
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
            "--ground-truth-mode",
        ]

        with patch("sys.argv", test_args):
            with patch("marc_pd_tool.cli.MarcCopyrightAnalyzer") as mock_analyzer_class:
                with patch("marc_pd_tool.cli.set_up_logging") as mock_logging:
                    with patch("marc_pd_tool.cli.RunIndexManager") as mock_run_index:
                        with patch("marc_pd_tool.cli.logger"):
                            mock_analyzer = create_mock_analyzer()
                            # Mock ground truth methods
                            mock_stats = Mock()
                            mock_stats.marc_with_lccn = 100
                            mock_stats.marc_lccn_coverage = 50.0
                            mock_stats.registration_matches = 20
                            mock_stats.renewal_matches = 10
                            mock_stats.total_marc_records = 200

                            mock_analyzer.extract_ground_truth.return_value = ([], mock_stats)
                            mock_analyzer.analyze_ground_truth_scores = Mock()
                            mock_analyzer.export_ground_truth_analysis = Mock()
                            mock_analyzer_class.return_value = mock_analyzer
                            mock_logging.return_value = None
                            mock_run_index.return_value = create_mock_run_index_manager()

                            main()

                            # Verify ground truth methods were called
                            mock_analyzer.extract_ground_truth.assert_called_once()
                            mock_analyzer.analyze_ground_truth_scores.assert_called_once()
                            mock_analyzer.export_ground_truth_analysis.assert_called_once()


class TestLogRunSummaryFunction:
    """Test log_run_summary function directly (covers lines 362-390)"""

    def test_log_run_summary_complete_execution(self):
        """Test complete execution of log_run_summary"""
        results_stats = {
            "total_records": 1000,
            "registration_matches": 200,
            "renewal_matches": 150,
            "pd_us_not_renewed": 100,
            "pd_pre_min_year": 50,
            "in_copyright": 150,
            "research_us_status": 600,
            "research_us_only_pd": 50,
            "country_unknown": 50,
        }

        mock_args = Mock()
        mock_args.output_formats = ["csv", "json"]

        with patch("marc_pd_tool.cli.logger") as mock_logger:
            log_run_summary(10.5, results_stats, "output.csv", mock_args)

            # Verify all log lines were called
            assert mock_logger.info.call_count >= 15  # Should log many lines

            # Check specific calls by getting the actual logged strings
            info_calls = [call.args[0] for call in mock_logger.info.call_args_list if call.args]

            # Check header
            assert any("=" * 80 in call for call in info_calls)
            assert any("PROCESSING COMPLETE" in call for call in info_calls)

            # Check statistics
            assert any("Total records processed: 1,000" in call for call in info_calls)
            assert any("Registration matches: 200" in call for call in info_calls)
            assert any("Renewal matches: 150" in call for call in info_calls)
            # Check for the processing time with .2f format
            assert any("Processing time:" in call and "seconds" in call for call in info_calls)
            assert any("records/minute" in call for call in info_calls)
            assert any("Output written to: output.csv" in call for call in info_calls)

            # Check copyright status breakdown
            assert any("Copyright Status Breakdown:" in call for call in info_calls)
            assert any("PD_US_NOT_RENEWED: 100" in call for call in info_calls)
            assert any("IN_COPYRIGHT: 150" in call for call in info_calls)
            assert any("RESEARCH_US_STATUS: 600" in call for call in info_calls)

    def test_log_run_summary_handles_zero_duration(self):
        """Test log_run_summary with zero duration"""
        results_stats = {"total_records": 10, "registration_matches": 2, "renewal_matches": 1}

        mock_args = Mock()
        mock_args.output_formats = ["csv"]

        with patch("marc_pd_tool.cli.logger") as mock_logger:
            # Should not crash with zero duration
            log_run_summary(0.0, results_stats, "output.csv", mock_args)

            # Verify it still logs
            assert mock_logger.info.call_count > 5
