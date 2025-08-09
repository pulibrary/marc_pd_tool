# tests/test_cli/test_cli_full_coverage.py

"""Comprehensive test suite to achieve 100% coverage for cli.py"""

# Standard library imports
from argparse import Namespace
from logging import getLogger
from unittest.mock import MagicMock
from unittest.mock import patch

# Third party imports
import pytest

# Local imports
from marc_pd_tool.cli import create_argument_parser
from marc_pd_tool.cli import generate_output_filename
from marc_pd_tool.cli import log_run_summary
from marc_pd_tool.cli import main

logger = getLogger(__name__)


class TestLogRunSummaryFullCoverage:
    """Test log_run_summary for full coverage"""

    def test_log_run_summary_with_skipped_records(self) -> None:
        """Test log_run_summary with skipped_no_year > 0"""
        args = Namespace(output_filename="test.csv")

        stats = {
            "total_records": 1000,
            "skipped_no_year": 50,
            "registration_matches": 100,
            "renewal_matches": 50,
        }

        with patch("marc_pd_tool.cli.logger") as mock_logger:
            log_run_summary(1.0, stats, "output.csv", args)

            # Check that skipped records were logged
            info_calls = [str(call) for call in mock_logger.info.call_args_list]
            assert any("Records skipped (no year): 50" in call for call in info_calls)

    def test_log_run_summary_foreign_status_grouping(self) -> None:
        """Test foreign status grouping in log_run_summary"""
        args = Namespace(output_filename="test.csv")

        stats = {
            "total_records": 1000,
            "registration_matches": 100,
            "renewal_matches": 50,
            # Various foreign statuses that should be grouped
            "foreign_renewed_fr": 10,
            "foreign_renewed_gb": 5,
            "foreign_renewed_invalid": 3,  # Invalid country code
            "foreign_registered_not_renewed_de": 7,
            "foreign_no_match_it": 20,
            "foreign_pre_1929_es": 15,
            "foreign_pre_1930_fr": 8,
        }

        with patch("marc_pd_tool.cli.logger") as mock_logger:
            log_run_summary(1.0, stats, "output.csv", args)

            info_calls = [str(call) for call in mock_logger.info.call_args_list]

            # Check that foreign statuses were grouped
            assert any("FOREIGN RENEWED: 18" in call for call in info_calls)  # 10+5+3
            assert any("FOREIGN REGISTERED NOT RENEWED: 7" in call for call in info_calls)
            assert any("FOREIGN NO MATCH: 20" in call for call in info_calls)
            assert any("FOREIGN PRE 1929: 15" in call for call in info_calls)
            assert any("FOREIGN PRE 1930: 8" in call for call in info_calls)

    def test_log_run_summary_unknown_foreign_pattern(self) -> None:
        """Test handling of unknown foreign status pattern"""
        args = Namespace(output_filename="test.csv")

        stats = {
            "total_records": 1000,
            "registration_matches": 100,
            "renewal_matches": 50,
            "foreign_unknown_pattern": 5,  # Unknown pattern
        }

        with patch("marc_pd_tool.cli.logger") as mock_logger:
            log_run_summary(1.0, stats, "output.csv", args)

            info_calls = [str(call) for call in mock_logger.info.call_args_list]

            # Should use the status as-is (but uppercase and with spaces)
            assert any("FOREIGN UNKNOWN PATTERN: 5" in call for call in info_calls)

    def test_log_run_summary_other_statuses(self) -> None:
        """Test logging of OUT_OF_DATA_RANGE statuses without year filters"""
        args = Namespace(output_filename="test.csv", min_year=None, max_year=None)

        stats = {
            "total_records": 1000,
            "registration_matches": 100,
            "renewal_matches": 50,
            "out_of_data_range_1992": 25,
        }

        with patch("marc_pd_tool.cli.logger") as mock_logger:
            log_run_summary(1.0, stats, "output.csv", args)

            info_calls = [str(call) for call in mock_logger.info.call_args_list]

            # Check Other section - should show plain OUT OF DATA RANGE when no year filters
            assert any("Other:" in call for call in info_calls)
            assert any("OUT OF DATA RANGE 1992: 25" in call for call in info_calls)

    def test_log_run_summary_out_of_range_with_both_years(self) -> None:
        """Test OUT_OF_DATA_RANGE display with both min and max years"""
        args = Namespace(output_filename="test.csv", min_year=1923, max_year=1977)

        stats = {
            "total_records": 1000,
            "registration_matches": 100,
            "renewal_matches": 50,
            "out_of_data_range": 30,
        }

        with patch("marc_pd_tool.cli.logger") as mock_logger:
            log_run_summary(1.0, stats, "output.csv", args)

            info_calls = [str(call) for call in mock_logger.info.call_args_list]

            # Should show year range
            assert any("OUT OF DATA RANGE (< 1923 or > 1977): 30" in call for call in info_calls)

    def test_log_run_summary_out_of_range_with_min_year_only(self) -> None:
        """Test OUT_OF_DATA_RANGE display with only min year"""
        args = Namespace(output_filename="test.csv", min_year=1923, max_year=None)

        stats = {
            "total_records": 1000,
            "registration_matches": 100,
            "renewal_matches": 50,
            "out_of_data_range": 15,
        }

        with patch("marc_pd_tool.cli.logger") as mock_logger:
            log_run_summary(1.0, stats, "output.csv", args)

            info_calls = [str(call) for call in mock_logger.info.call_args_list]

            # Should show only min year
            assert any("OUT OF DATA RANGE (< 1923): 15" in call for call in info_calls)

    def test_log_run_summary_out_of_range_with_max_year_only(self) -> None:
        """Test OUT_OF_DATA_RANGE display with only max year"""
        args = Namespace(output_filename="test.csv", min_year=None, max_year=1977)

        stats = {
            "total_records": 1000,
            "registration_matches": 100,
            "renewal_matches": 50,
            "out_of_data_range": 20,
        }

        with patch("marc_pd_tool.cli.logger") as mock_logger:
            log_run_summary(1.0, stats, "output.csv", args)

            info_calls = [str(call) for call in mock_logger.info.call_args_list]

            # Should show only max year
            assert any("OUT OF DATA RANGE (> 1977): 20" in call for call in info_calls)


class TestGenerateOutputFilenameFullCoverage:
    """Test generate_output_filename for full coverage"""

    def test_filename_with_long_extension(self) -> None:
        """Test that long extensions are not removed"""
        # Standard library imports
        from re import match

        args = Namespace(
            output_filename="test.longext",  # Extension > 4 chars
            us_only=False,
            min_year=None,
            max_year=None,
            score_everything_mode=False,
        )

        result = generate_output_filename(args)

        # Long extension should be preserved with timestamp
        pattern = r"^reports/\d{8}_\d{6}_test\.longext$"
        assert match(pattern, result), f"Expected pattern {pattern}, got {result}"

    def test_filename_with_dots_in_path(self) -> None:
        """Test filename with dots in the path"""
        # Standard library imports
        from re import match

        args = Namespace(
            output_filename="my.project/test.csv",
            us_only=False,
            min_year=None,
            max_year=None,
            score_everything_mode=False,
        )

        result = generate_output_filename(args)

        # Should only remove the last .csv with timestamp added
        pattern = r"^my\.project/\d{8}_\d{6}_test$"
        assert match(pattern, result), f"Expected pattern {pattern}, got {result}"

    def test_ground_truth_mode_filename(self) -> None:
        """Test filename generation for ground_truth_mode"""
        # Standard library imports
        from re import match

        args = Namespace(
            output_filename="matches.csv",  # Default
            ground_truth_mode=True,
            us_only=False,
            min_year=None,
            max_year=None,
            score_everything_mode=False,
        )

        result = generate_output_filename(args)

        # Should use "ground_truth" instead of "matches" with timestamp
        pattern = r"^reports/\d{8}_\d{6}_ground_truth$"
        assert match(pattern, result), f"Expected pattern {pattern}, got {result}"


class TestMainFunctionFullCoverage:
    """Test main function for full coverage"""

    def test_main_with_min_year_logging(self) -> None:
        """Test that min_year is logged when provided"""
        test_args = ["marc_pd_tool", "--marcxml", "test.xml", "--min-year", "1950"]

        with patch("sys.argv", test_args):
            with patch("marc_pd_tool.cli.MarcCopyrightAnalyzer") as MockAnalyzer:
                mock_analyzer = MagicMock()
                mock_results = MagicMock()
                mock_results.statistics = {
                    "total_records": 100,
                    "registration_matches": 10,
                    "renewal_matches": 5,
                }
                mock_analyzer.analyze_marc_file.return_value = mock_results
                MockAnalyzer.return_value = mock_analyzer

                with patch("marc_pd_tool.cli.logger") as mock_logger:
                    with patch("marc_pd_tool.cli.RunIndexManager") as MockRunIndex:
                        mock_run_mgr = MagicMock()
                        MockRunIndex.return_value = mock_run_mgr

                        main()

                        # Check that min_year was logged
                        info_calls = [str(call) for call in mock_logger.info.call_args_list]
                        assert any("Using min_year filter: 1950" in call for call in info_calls)

    def test_main_year_validation_error(self) -> None:
        """Test main with max_year < min_year"""
        test_args = [
            "marc_pd_tool",
            "--marcxml",
            "test.xml",
            "--min-year",
            "1960",
            "--max-year",
            "1950",  # Invalid: max < min
        ]

        with patch("sys.argv", test_args):
            with pytest.raises(ValueError, match="Max year .* cannot be less than min year"):
                main()

    def test_main_with_memory_monitoring(self) -> None:
        """Test main with memory monitoring enabled"""
        test_args = [
            "marc_pd_tool",
            "--marcxml",
            "test.xml",
            "--monitor-memory",
            "--memory-log-interval",
            "30",
        ]

        with patch("sys.argv", test_args):
            with patch("marc_pd_tool.cli.MarcCopyrightAnalyzer") as MockAnalyzer:
                mock_analyzer = MagicMock()
                mock_results = MagicMock()
                mock_results.statistics = {
                    "total_records": 100,
                    "registration_matches": 10,
                    "renewal_matches": 5,
                }
                mock_analyzer.analyze_marc_file.return_value = mock_results
                MockAnalyzer.return_value = mock_analyzer

                with patch("marc_pd_tool.utils.memory_utils.MemoryMonitor") as MockMonitor:
                    mock_monitor = MagicMock()
                    mock_monitor.get_final_summary.return_value = "Memory summary"
                    MockMonitor.return_value = mock_monitor

                    with patch("marc_pd_tool.cli.RunIndexManager") as MockRunIndex:
                        mock_run_mgr = MagicMock()
                        MockRunIndex.return_value = mock_run_mgr

                        with patch("marc_pd_tool.cli.logger") as mock_logger:
                            main()

                            # Check that memory monitor was used
                            MockMonitor.assert_called_once_with(log_interval=30)
                            mock_monitor.force_log.assert_any_call("before processing")
                            mock_monitor.force_log.assert_any_call("after processing")

                            # Check final summary was logged
                            info_calls = [str(call) for call in mock_logger.info.call_args_list]
                            assert any("Memory summary" in call for call in info_calls)

    def test_main_creates_output_directory(self) -> None:
        """Test that main creates output directory if it doesn't exist"""
        test_args = [
            "marc_pd_tool",
            "--marcxml",
            "test.xml",
            "--output-filename",
            "custom_dir/output.csv",
        ]

        with patch("sys.argv", test_args):
            with patch("marc_pd_tool.cli.MarcCopyrightAnalyzer") as MockAnalyzer:
                mock_analyzer = MagicMock()
                mock_results = MagicMock()
                mock_results.statistics = {
                    "total_records": 100,
                    "registration_matches": 10,
                    "renewal_matches": 5,
                }
                mock_analyzer.analyze_marc_file.return_value = mock_results
                MockAnalyzer.return_value = mock_analyzer

                with patch("marc_pd_tool.cli.makedirs") as mock_makedirs:
                    with patch("marc_pd_tool.cli.RunIndexManager") as MockRunIndex:
                        mock_run_mgr = MagicMock()
                        MockRunIndex.return_value = mock_run_mgr

                        main()

                        # Check that makedirs was called
                        mock_makedirs.assert_called_once_with("custom_dir", exist_ok=True)

    def test_main_exception_handling(self) -> None:
        """Test main function exception handling"""
        test_args = ["marc_pd_tool", "--marcxml", "test.xml"]

        with patch("sys.argv", test_args):
            with patch("marc_pd_tool.cli.MarcCopyrightAnalyzer") as MockAnalyzer:
                # Make analyzer raise an exception
                MockAnalyzer.side_effect = Exception("Test error")

                with patch("marc_pd_tool.cli.RunIndexManager") as MockRunIndex:
                    mock_run_mgr = MagicMock()
                    MockRunIndex.return_value = mock_run_mgr

                    with patch("marc_pd_tool.cli.logger") as mock_logger:
                        with pytest.raises(Exception, match="Test error"):
                            main()

                        # Check that error was logged
                        mock_logger.error.assert_called_once()
                        assert "Test error" in mock_logger.error.call_args[0][0]

                        # Check that run status was updated to failed
                        update_calls = mock_run_mgr.update_run.call_args_list
                        last_call = update_calls[-1]
                        assert last_call[0][1]["status"] == "failed"


class TestCreateArgumentParserFullCoverage:
    """Test create_argument_parser for full coverage"""

    def test_parser_has_all_arguments(self) -> None:
        """Test that parser has all expected arguments"""
        parser = create_argument_parser()

        # Parse with minimal required args
        args = parser.parse_args(["--marcxml", "test.xml"])

        # Check that all attributes exist
        assert hasattr(args, "marcxml")
        assert hasattr(args, "copyright_dir")
        assert hasattr(args, "renewal_dir")
        assert hasattr(args, "output_filename")
        assert hasattr(args, "output_formats")
        assert hasattr(args, "single_file")
        assert hasattr(args, "batch_size")
        assert hasattr(args, "max_workers")
        assert hasattr(args, "monitor_memory")
        assert hasattr(args, "memory_log_interval")
        assert hasattr(args, "title_threshold")
        assert hasattr(args, "author_threshold")
        assert hasattr(args, "publisher_threshold")
        assert hasattr(args, "year_tolerance")
        assert hasattr(args, "early_exit_title")
        assert hasattr(args, "early_exit_author")
        assert hasattr(args, "early_exit_publisher")
        assert hasattr(args, "min_year")
        assert hasattr(args, "max_year")
        assert hasattr(args, "us_only")
        assert hasattr(args, "score_everything_mode")
        assert hasattr(args, "minimum_combined_score")
        assert hasattr(args, "brute_force_missing_year")
        assert hasattr(args, "generic_title_threshold")
        assert hasattr(args, "disable_generic_detection")
        assert hasattr(args, "ground_truth_mode")
        assert hasattr(args, "config")
        assert hasattr(args, "cache_dir")
        assert hasattr(args, "force_refresh")
        assert hasattr(args, "disable_cache")
        assert hasattr(args, "log_file")
        assert hasattr(args, "debug")
        assert hasattr(args, "no_log_file")


class TestEdgeCasesFullCoverage:
    """Test edge cases for full coverage"""

    def test_generate_output_filename_no_directory(self) -> None:
        """Test generate_output_filename when dirname returns empty string"""
        # Standard library imports
        from re import match

        args = Namespace(
            output_filename="output.csv",  # No directory
            us_only=False,
            min_year=None,
            max_year=None,
            score_everything_mode=False,
        )

        with patch("marc_pd_tool.cli.dirname", return_value=""):
            result = generate_output_filename(args)

            # Should add reports/ directory with timestamp
            pattern = r"^reports/\d{8}_\d{6}_output$"
            assert match(pattern, result), f"Expected pattern {pattern}, got {result}"

    def test_log_run_summary_foreign_pre_without_year(self) -> None:
        """Test foreign PRE status without year number"""
        args = Namespace(output_filename="test.csv")

        stats = {
            "total_records": 1000,
            "registration_matches": 100,
            "renewal_matches": 50,
            "foreign_pre_invalid": 5,  # PRE without proper year
        }

        with patch("marc_pd_tool.cli.logger") as mock_logger:
            log_run_summary(1.0, stats, "output.csv", args)

            info_calls = [str(call) for call in mock_logger.info.call_args_list]

            # Should use fallback "FOREIGN_PRE"
            assert any("FOREIGN PRE: 5" in call for call in info_calls)

    def test_log_run_summary_skip_zero_counts(self) -> None:
        """Test that statuses with zero count are skipped"""
        args = Namespace(output_filename="test.csv")

        stats = {
            "total_records": 1000,
            "registration_matches": 100,
            "renewal_matches": 50,
            "us_renewed": 0,  # Zero count - should be skipped
            "us_no_match": 10,
        }

        with patch("marc_pd_tool.cli.logger") as mock_logger:
            log_run_summary(1.0, stats, "output.csv", args)

            info_calls = [str(call) for call in mock_logger.info.call_args_list]

            # US_RENEWED should not appear (zero count)
            assert not any("US RENEWED" in call for call in info_calls)
            # US_NO_MATCH should appear
            assert any("US NO MATCH: 10" in call for call in info_calls)
