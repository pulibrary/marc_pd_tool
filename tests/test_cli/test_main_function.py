# tests/test_cli/test_main_function.py

"""Tests for the main() function and CLI execution"""

# Standard library imports
from unittest.mock import Mock
from unittest.mock import patch

# Third party imports
import pytest

# Local imports
from marc_pd_tool.cli import log_run_summary
from marc_pd_tool.cli import main


def create_mock_statistics(total=100, reg_matches=10, ren_matches=5):
    """Create complete mock statistics dict"""
    return {
        "total_records": total,
        "registration_matches": reg_matches,
        "renewal_matches": ren_matches,
        "us_records": total,
        "non_us_records": 0,
        "unknown_country": 0,
        "no_matches": total - reg_matches - ren_matches,
        "us_registered_not_renewed": 25,
        "us_pre_1929": 10,
        "us_renewed": 30,
        "foreign_no_match_gbr": 30,
        "foreign_renewed_fra": 5,
        "country_unknown_no_match": 0,
    }


class TestMainFunction:
    """Test the main() function"""

    def test_main_basic_execution(self):
        """Test basic execution of main() with minimal args"""
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
                            # Mock analyzer
                            mock_analyzer = Mock()
                            mock_analyzer_class.return_value = mock_analyzer

                            # Mock analyze_marc_file to return AnalysisResults
                            mock_results = Mock()
                            mock_results.statistics = create_mock_statistics()
                            mock_analyzer.analyze_marc_file.return_value = mock_results

                            mock_logging.return_value = "/path/to/log.log"

                            # Mock run index manager
                            mock_run_index.return_value.add_run.return_value = None
                            mock_run_index.return_value.update_run.return_value = None

                            # Call main
                            main()

                            # Verify key functions were called
                            mock_logging.assert_called_once()
                            mock_analyzer.analyze_marc_file.assert_called()
                            mock_summary.assert_called_once()

    def test_main_with_year_validation_error(self):
        """Test main() with invalid year range"""
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
            "1960",
            "--max-year",
            "1950",  # Invalid: max < min
        ]

        with patch("sys.argv", test_args):
            with pytest.raises(ValueError, match="Max year.*cannot be less than min year"):
                main()

    def test_main_with_score_everything_mode(self):
        """Test main() with score everything mode forcing single file"""
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
        ]

        with patch("sys.argv", test_args):
            with patch("marc_pd_tool.cli.MarcCopyrightAnalyzer") as mock_analyzer_class:
                with patch("marc_pd_tool.cli.set_up_logging"):
                    with patch("marc_pd_tool.cli.log_run_summary"):
                        # Mock analyzer
                        mock_analyzer = Mock()
                        mock_analyzer_class.return_value = mock_analyzer
                        # Mock analyze_marc_file to return AnalysisResults
                        mock_results = Mock()
                        mock_results.statistics = create_mock_statistics()
                        mock_analyzer.analyze_marc_file.return_value = mock_results

                        main()

                        # In score_everything mode, single_file should be True
                        # This is checked in the args processing
                        # We can't directly verify it here, but the test passes if no error

    def test_main_with_custom_workers(self):
        """Test main() with custom number of workers"""
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
            "--max-workers",
            "4",
        ]

        with patch("sys.argv", test_args):
            with patch("marc_pd_tool.cli.MarcCopyrightAnalyzer") as mock_analyzer_class:
                with patch("marc_pd_tool.cli.set_up_logging"):
                    with patch("marc_pd_tool.cli.log_run_summary"):
                        # Mock analyzer
                        mock_analyzer = Mock()
                        mock_analyzer_class.return_value = mock_analyzer
                        # Mock analyze_marc_file to return AnalysisResults
                        mock_results = Mock()
                        mock_results.statistics = create_mock_statistics()
                        mock_analyzer.analyze_marc_file.return_value = mock_results

                        main()

                        # Verify analyze_marc_file was called with correct options
                        call_kwargs = mock_analyzer.analyze_marc_file.call_args[1]
                        assert call_kwargs["options"]["num_processes"] == 4

    def test_main_with_default_workers(self):
        """Test main() with default number of workers"""
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
                with patch("marc_pd_tool.cli.set_up_logging"):
                    with patch("marc_pd_tool.cli.log_run_summary"):
                        with patch("marc_pd_tool.cli.cpu_count", return_value=8):
                            # Mock analyzer
                            mock_analyzer = Mock()
                            mock_analyzer_class.return_value = mock_analyzer
                            # Mock analyze_marc_file to return AnalysisResults
                            mock_results = Mock()
                            mock_results.statistics = create_mock_statistics()
                            mock_analyzer.analyze_marc_file.return_value = mock_results

                            main()

                            # Verify analyze_marc_file was called with default workers
                            call_kwargs = mock_analyzer.analyze_marc_file.call_args[1]
                            assert call_kwargs["options"]["num_processes"] == 6  # 8 - 2

    def test_main_with_no_log_file(self):
        """Test main() with logging disabled"""
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
            "--no-log-file",
        ]

        with patch("sys.argv", test_args):
            with patch("marc_pd_tool.cli.MarcCopyrightAnalyzer") as mock_analyzer_class:
                with patch("marc_pd_tool.cli.set_up_logging") as mock_logging:
                    with patch("marc_pd_tool.cli.log_run_summary"):
                        # Mock analyzer
                        mock_analyzer = Mock()
                        mock_analyzer_class.return_value = mock_analyzer
                        # Mock analyze_marc_file to return AnalysisResults
                        mock_results = Mock()
                        mock_results.statistics = create_mock_statistics()
                        mock_analyzer.analyze_marc_file.return_value = mock_results
                        mock_logging.return_value = None  # No log file

                        main()

                        # Verify logging was set up with use_default_log=False
                        call_args = mock_logging.call_args[1]
                        assert call_args["use_default_log"] is False

    def test_main_ground_truth_mode(self):
        """Test main() in ground truth mode"""
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
                with patch("marc_pd_tool.cli.set_up_logging"):
                    with patch("marc_pd_tool.cli.log_run_summary"):
                        # Mock analyzer
                        mock_analyzer = Mock()
                        mock_analyzer_class.return_value = mock_analyzer

                        # Mock ground truth extraction
                        mock_stats = Mock()
                        mock_stats.marc_with_lccn = 100
                        mock_stats.marc_lccn_coverage = 50.0
                        mock_stats.registration_matches = 20
                        mock_stats.renewal_matches = 10
                        mock_stats.total_marc_records = 200

                        # Return some mock ground truth pairs so export gets called
                        mock_pair = Mock()
                        mock_analyzer.extract_ground_truth.return_value = ([mock_pair], mock_stats)

                        main()

                        # Verify ground truth methods were called
                        mock_analyzer.extract_ground_truth.assert_called_once()
                        mock_analyzer.export_ground_truth_analysis.assert_called_once()


class TestLogRunSummary:
    """Test the log_run_summary function"""

    def test_log_run_summary_basic(self):
        """Test basic log run summary output"""
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

        with patch("marc_pd_tool.cli.logger") as mock_logger:
            # Create mock args
            mock_args = Mock()
            log_run_summary(10.5, results_stats, "output.csv", mock_args)

            # Verify key information was logged
            assert mock_logger.info.call_count > 10

            # Check specific calls by getting the actual logged strings
            info_calls = [call.args[0] for call in mock_logger.info.call_args_list if call.args]
            assert any("Total records processed: 1,000" in call for call in info_calls)
            assert any("Registration matches: 200" in call for call in info_calls)
            # Check for the processing time with .2f format
            assert any("Processing time:" in call and "seconds" in call for call in info_calls)
            assert any("output.csv" in call for call in info_calls)

    def test_log_run_summary_with_zero_duration(self):
        """Test log run summary with zero duration"""
        results_stats = {"total_records": 100, "registration_matches": 10, "renewal_matches": 5}

        with patch("marc_pd_tool.cli.logger") as mock_logger:
            # Create mock args
            mock_args = Mock()
            log_run_summary(0.0, results_stats, "output.csv", mock_args)

            # Should not crash with zero duration
            assert mock_logger.info.call_count > 5

    def test_log_run_summary_with_missing_status_fields(self):
        """Test log run summary with some status fields missing"""
        results_stats = {
            "total_records": 100,
            "registration_matches": 10,
            "renewal_matches": 5,
            "us_registered_not_renewed": 25,
            "us_renewed": 30,
            # Missing some status fields
        }

        with patch("marc_pd_tool.cli.logger") as mock_logger:
            # Create mock args
            mock_args = Mock()
            log_run_summary(5.0, results_stats, "output.csv", mock_args)

            # Should handle missing fields gracefully
            assert mock_logger.info.call_count > 5

            # Check that present fields are logged (new consolidated format)
            info_calls = [call.args[0] for call in mock_logger.info.call_args_list if call.args]
            assert any("US REGISTERED NOT RENEWED: 25" in call for call in info_calls)
            assert any("US RENEWED: 30" in call for call in info_calls)


class TestProcessingErrors:
    """Test error handling in main()"""

    def test_main_handles_processing_error(self):
        """Test main() handles errors from processing"""
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
                with patch("marc_pd_tool.cli.set_up_logging"):
                    # Mock analyzer error
                    mock_analyzer_class.side_effect = Exception("Processing failed")

                    # Should raise the exception
                    with pytest.raises(Exception, match="Processing failed"):
                        main()

    def test_main_with_min_year_logging(self):
        """Test that min_year is logged when provided"""
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
                with patch("marc_pd_tool.cli.set_up_logging"):
                    with patch("marc_pd_tool.cli.log_run_summary"):
                        with patch("marc_pd_tool.cli.logger") as mock_logger:
                            # Mock analyzer
                            mock_analyzer = Mock()
                            mock_analyzer_class.return_value = mock_analyzer
                            # Mock analyze_marc_file to return AnalysisResults
                            mock_results = Mock()
                            mock_results.statistics = create_mock_statistics()
                            mock_analyzer.analyze_marc_file.return_value = mock_results

                            main()

                            # Verify min_year was logged
                            calls = [str(call) for call in mock_logger.info.call_args_list]
                            assert any("Using min_year filter: 1950" in str(call) for call in calls)
