# tests/test_cli/test_dynamic_filenames.py

"""Tests for dynamic filename generation functionality"""

# Standard library imports
from argparse import Namespace

# Third party imports
from pytest import fixture

# Local imports
# Local imports - import CLI functions from new location
from marc_pd_tool.cli import generate_output_filename


class TestDynamicFilenames:
    """Test dynamic filename generation functionality"""

    @fixture
    def base_args(self):
        """Create base args namespace for testing"""
        return Namespace(
            output_filename="matches.csv",
            us_only=False,
            min_year=None,
            max_year=None,
            score_everything_mode=False,
            output_formats=["csv"],
        )

    def test_user_provided_filename_gets_correct_extension(self, base_args):
        """Test that user-provided filenames get extensions stripped (added by exporters)"""
        # Standard library imports
        import re

        base_args.output_filename = "my_custom_analysis.csv"
        result = generate_output_filename(base_args)
        pattern = r"reports/\d{8}_\d{6}_my_custom_analysis"
        assert re.match(pattern, result), f"Expected timestamp pattern, got: {result}"

        # Extension should be stripped regardless of format
        base_args.output_formats = ["xlsx"]
        base_args.output_filename = "my_custom_analysis.xlsx"
        result = generate_output_filename(base_args)
        pattern = r"reports/\d{8}_\d{6}_my_custom_analysis"
        assert re.match(pattern, result), f"Expected timestamp pattern, got: {result}"

    def test_user_provided_filename_with_path_gets_correct_extension(self, base_args):
        """Test that user-provided filenames with paths get correct extension"""
        # Standard library imports
        import re

        base_args.output_filename = "/path/to/my_analysis.csv"
        result = generate_output_filename(base_args)
        pattern = r"/path/to/\d{8}_\d{6}_my_analysis"
        assert re.match(pattern, result), f"Expected timestamp pattern, got: {result}"

        # Extension should be stripped regardless of format
        base_args.output_formats = ["json"]
        base_args.output_filename = "/path/to/my_analysis.json"
        result = generate_output_filename(base_args)
        pattern = r"/path/to/\d{8}_\d{6}_my_analysis"
        assert re.match(pattern, result), f"Expected timestamp pattern, got: {result}"

    def test_default_filename_no_filters(self, base_args):
        """Test default filename when no filters are applied"""
        # Standard library imports
        import re

        result = generate_output_filename(base_args)
        pattern = r"reports/\d{8}_\d{6}_matches"
        assert re.match(pattern, result), f"Expected timestamp pattern, got: {result}"

    def test_us_only_filter_adds_suffix(self, base_args):
        """Test that US-only filter adds us-only suffix"""
        # Standard library imports
        import re

        base_args.us_only = True
        result = generate_output_filename(base_args)
        pattern = r"reports/\d{8}_\d{6}_matches_us-only"
        assert re.match(pattern, result), f"Expected timestamp pattern, got: {result}"

    def test_year_range_filter(self, base_args):
        """Test filename generation with year range"""
        # Standard library imports
        import re

        base_args.min_year = 1950
        base_args.max_year = 1960
        result = generate_output_filename(base_args)
        pattern = r"reports/\d{8}_\d{6}_matches_1950-1960"
        assert re.match(pattern, result), f"Expected timestamp pattern, got: {result}"

    def test_single_year_filter(self, base_args):
        """Test filename generation when min_year equals max_year"""
        # Standard library imports
        import re

        base_args.min_year = 1955
        base_args.max_year = 1955
        result = generate_output_filename(base_args)
        pattern = r"reports/\d{8}_\d{6}_matches_1955-1955"
        assert re.match(pattern, result), f"Expected timestamp pattern, got: {result}"

    def test_min_year_only_filter(self, base_args):
        """Test filename generation with only minimum year"""
        # Standard library imports
        import re

        base_args.min_year = 1945
        result = generate_output_filename(base_args)
        pattern = r"reports/\d{8}_\d{6}_matches_1945-current"
        assert re.match(pattern, result), f"Expected timestamp pattern, got: {result}"

    def test_max_year_only_filter(self, base_args):
        """Test filename generation with only maximum year"""
        # Standard library imports
        import re

        base_args.max_year = 1970
        result = generate_output_filename(base_args)
        pattern = r"reports/\d{8}_\d{6}_matches_pre-1970"
        assert re.match(pattern, result), f"Expected timestamp pattern, got: {result}"

    def test_combined_us_only_and_year_range(self, base_args):
        """Test filename generation with both US-only and year range filters"""
        # Standard library imports
        import re

        base_args.us_only = True
        base_args.min_year = 1950
        base_args.max_year = 1960
        result = generate_output_filename(base_args)
        pattern = r"reports/\d{8}_\d{6}_matches_us-only_1950-1960"
        assert re.match(pattern, result), f"Expected timestamp pattern, got: {result}"

    def test_combined_us_only_and_single_year(self, base_args):
        """Test filename generation with US-only and single year"""
        # Standard library imports
        import re

        base_args.us_only = True
        base_args.min_year = 1955
        base_args.max_year = 1955
        result = generate_output_filename(base_args)
        pattern = r"reports/\d{8}_\d{6}_matches_us-only_1955-1955"
        assert re.match(pattern, result), f"Expected timestamp pattern, got: {result}"

    def test_combined_us_only_and_min_year(self, base_args):
        """Test filename generation with US-only and minimum year only"""
        # Standard library imports
        import re

        base_args.us_only = True
        base_args.min_year = 1945
        result = generate_output_filename(base_args)
        pattern = r"reports/\d{8}_\d{6}_matches_us-only_1945-current"
        assert re.match(pattern, result), f"Expected timestamp pattern, got: {result}"

    def test_combined_us_only_and_max_year(self, base_args):
        """Test filename generation with US-only and maximum year only"""
        # Standard library imports
        import re

        base_args.us_only = True
        base_args.max_year = 1970
        result = generate_output_filename(base_args)
        pattern = r"reports/\d{8}_\d{6}_matches_us-only_pre-1970"
        assert re.match(pattern, result), f"Expected timestamp pattern, got: {result}"

    def test_score_everything_indicator(self, base_args):
        """Test filename includes score-everything indicator when enabled"""
        # Standard library imports
        import re

        base_args.score_everything_mode = True
        result = generate_output_filename(base_args)
        pattern = r"reports/\d{8}_\d{6}_matches_score-everything"
        assert re.match(pattern, result), f"Expected timestamp pattern, got: {result}"

    def test_score_everything_with_filters(self, base_args):
        """Test filename with score-everything and other filters"""
        # Standard library imports
        import re

        base_args.score_everything_mode = True
        base_args.us_only = True
        base_args.min_year = 1930
        base_args.max_year = 1960
        result = generate_output_filename(base_args)
        pattern = r"reports/\d{8}_\d{6}_matches_us-only_1930-1960_score-everything"
        assert re.match(pattern, result), f"Expected timestamp pattern, got: {result}"


class TestFilenameEdgeCases:
    """Test edge cases and special scenarios"""

    def test_non_default_output_with_filters_gets_correct_extension(self):
        """Test that non-default output gets correct extension based on format"""
        # Standard library imports
        import re

        args = Namespace(
            output_filename="custom.csv",
            us_only=True,
            min_year=1950,
            max_year=1960,
            score_everything_mode=False,
            output_formats=["csv"],
        )
        result = generate_output_filename(args)
        pattern = r"reports/\d{8}_\d{6}_custom"
        assert re.match(pattern, result), f"Expected timestamp pattern, got: {result}"

        # Extension stripped regardless of format
        args.output_formats = ["xlsx"]
        result = generate_output_filename(args)
        assert re.match(pattern, result), f"Expected timestamp pattern, got: {result}"

    def test_output_with_different_extension(self):
        """Test that file extensions are replaced based on output format"""
        # Standard library imports
        import re

        args = Namespace(
            output_filename="data.tsv",
            us_only=True,
            min_year=1950,
            max_year=1960,
            score_everything_mode=False,
            output_formats=["csv"],
        )
        # Extension is stripped
        result = generate_output_filename(args)
        pattern = r"reports/\d{8}_\d{6}_data"
        assert re.match(pattern, result), f"Expected timestamp pattern, got: {result}"

        # Test with xlsx format
        args.output_formats = ["xlsx"]
        result = generate_output_filename(args)
        assert re.match(pattern, result), f"Expected timestamp pattern, got: {result}"

    def test_relative_path_preserved(self):
        """Test that relative paths are preserved"""
        # Standard library imports
        import re

        args = Namespace(
            output_filename="./results/analysis.csv",
            us_only=True,
            min_year=1950,
            max_year=None,
            score_everything_mode=False,
            output_formats=["csv"],
        )
        result = generate_output_filename(args)
        pattern = r"\./results/\d{8}_\d{6}_analysis"
        assert re.match(pattern, result), f"Expected timestamp pattern, got: {result}"

    def test_complex_filename_scenarios(self):
        """Test complex real-world scenarios"""
        # Standard library imports
        import re

        # Scenario 1: Research focused on 1950s US publications
        args1 = Namespace(
            output_filename="matches.csv",
            us_only=True,
            min_year=1950,
            max_year=1959,
            score_everything_mode=False,
            output_formats=["csv"],
        )
        result1 = generate_output_filename(args1)
        pattern1 = r"reports/\d{8}_\d{6}_matches_us-only_1950-1959"
        assert re.match(pattern1, result1), f"Expected timestamp pattern, got: {result1}"

        # Scenario 2: Everything after 1930
        args2 = Namespace(
            output_filename="matches.csv",
            us_only=False,
            min_year=1930,
            max_year=None,
            score_everything_mode=False,
            output_formats=["csv"],
        )
        result2 = generate_output_filename(args2)
        pattern2 = r"reports/\d{8}_\d{6}_matches_1930-current"
        assert re.match(pattern2, result2), f"Expected timestamp pattern, got: {result2}"

        # Scenario 3: US publications up to 1970
        args3 = Namespace(
            output_filename="matches.csv",
            us_only=True,
            min_year=None,
            max_year=1970,
            score_everything_mode=False,
            output_formats=["csv"],
        )
        result3 = generate_output_filename(args3)
        pattern3 = r"reports/\d{8}_\d{6}_matches_us-only_pre-1970"
        assert re.match(pattern3, result3), f"Expected timestamp pattern, got: {result3}"

    def test_default_detection_logic(self):
        """Test that only the exact default triggers dynamic naming"""
        # These should trigger dynamic naming
        args_default = Namespace(
            output_filename="matches.csv",
            us_only=True,
            min_year=1950,
            max_year=None,
            score_everything_mode=False,
            output_formats=["csv"],
        )
        result = generate_output_filename(args_default)
        assert "us-only" in result

        # These should NOT trigger dynamic naming (different from default)
        args_similar = Namespace(
            output_filename="matches2.csv",
            us_only=True,
            min_year=1950,
            max_year=None,
            score_everything_mode=False,
            output_formats=["csv"],
        )
        # Standard library imports
        import re

        result = generate_output_filename(args_similar)
        pattern = r"reports/\d{8}_\d{6}_matches2"
        assert re.match(pattern, result), f"Expected timestamp pattern, got: {result}"

        # Test extension stripped
        args_similar.output_formats = ["json"]
        result = generate_output_filename(args_similar)
        assert re.match(pattern, result), f"Expected timestamp pattern, got: {result}"

        args_case = Namespace(
            output_filename="Matches.csv",
            us_only=True,
            min_year=1950,
            max_year=None,
            score_everything_mode=False,
            output_formats=["csv"],
        )
        # Standard library imports
        import re

        result = generate_output_filename(args_case)
        pattern = r"reports/\d{8}_\d{6}_Matches"
        assert re.match(pattern, result), f"Expected timestamp pattern, got: {result}"

        # Test case preservation
        args_case.output_formats = ["xlsx"]
        result = generate_output_filename(args_case)
        assert re.match(pattern, result), f"Expected timestamp pattern, got: {result}"

    def test_filename_without_extension_gets_added(self):
        """Test that filenames without extensions get the correct extension added"""
        args = Namespace(
            output_filename="my_output",
            us_only=False,
            min_year=None,
            max_year=None,
            score_everything_mode=False,
            output_formats=["csv"],
        )
        # Standard library imports
        import re

        result = generate_output_filename(args)
        pattern = r"reports/\d{8}_\d{6}_my_output"
        assert re.match(pattern, result), f"Expected timestamp pattern, got: {result}"

        args.output_formats = ["xlsx"]
        result = generate_output_filename(args)
        assert re.match(pattern, result), f"Expected timestamp pattern, got: {result}"

        args.output_formats = ["json"]
        result = generate_output_filename(args)
        assert re.match(pattern, result), f"Expected timestamp pattern, got: {result}"


class TestTimestampedFilenames:
    """Test that all filenames get timestamp prefixes"""

    @fixture
    def base_args(self):
        """Create base args namespace for testing"""
        return Namespace(
            output_filename="matches.csv",
            us_only=False,
            min_year=None,
            max_year=None,
            score_everything_mode=False,
            ground_truth_mode=False,
            output_formats=["csv"],
        )

    def test_default_filename_gets_timestamp(self, base_args):
        """Test that default filename gets timestamp prefix"""
        # Standard library imports
        from datetime import datetime
        import re

        result = generate_output_filename(base_args)

        # Should match pattern: reports/YYYYMMDD_HHMMSS_matches
        pattern = r"reports/\d{8}_\d{6}_matches"
        assert re.match(pattern, result), f"Expected timestamp pattern, got: {result}"

        # Verify timestamp is recent (within last minute)
        timestamp_part = result.split("/")[1].split("_matches")[0]
        timestamp_str = timestamp_part.replace("_", "")
        timestamp_dt = datetime.strptime(timestamp_str, "%Y%m%d%H%M%S")
        now = datetime.now()
        time_diff = (now - timestamp_dt).total_seconds()
        assert time_diff < 60, f"Timestamp not recent: {timestamp_dt}"

    def test_user_provided_filename_gets_timestamp(self, base_args):
        """Test that user-provided filename gets timestamp prefix"""
        # Standard library imports
        import re

        base_args.output_filename = "custom_output.csv"
        result = generate_output_filename(base_args)

        # Should match pattern: reports/YYYYMMDD_HHMMSS_custom_output
        pattern = r"reports/\d{8}_\d{6}_custom_output"
        assert re.match(pattern, result), f"Expected timestamp pattern, got: {result}"

    def test_path_with_directory_preserves_directory(self, base_args):
        """Test that directory path is preserved and timestamp only added to filename"""
        # Standard library imports
        import re

        base_args.output_filename = "/custom/path/output.csv"
        result = generate_output_filename(base_args)

        # Should match pattern: /custom/path/YYYYMMDD_HHMMSS_output
        pattern = r"/custom/path/\d{8}_\d{6}_output"
        assert re.match(pattern, result), f"Expected timestamp pattern, got: {result}"

    def test_timestamp_with_filters(self, base_args):
        """Test that timestamp works with various filters"""
        # Standard library imports
        import re

        base_args.us_only = True
        base_args.min_year = 1950
        base_args.max_year = 1970
        result = generate_output_filename(base_args)

        # Should match pattern: reports/YYYYMMDD_HHMMSS_matches_us-only_1950-1970
        pattern = r"reports/\d{8}_\d{6}_matches_us-only_1950-1970"
        assert re.match(pattern, result), f"Expected timestamp pattern, got: {result}"

    def test_timestamp_with_ground_truth_mode(self, base_args):
        """Test that timestamp works with ground truth mode"""
        # Standard library imports
        import re

        base_args.ground_truth_mode = True
        result = generate_output_filename(base_args)

        # Should match pattern: reports/YYYYMMDD_HHMMSS_ground_truth
        pattern = r"reports/\d{8}_\d{6}_ground_truth"
        assert re.match(pattern, result), f"Expected timestamp pattern, got: {result}"

    def test_timestamp_with_score_everything(self, base_args):
        """Test that timestamp works with score-everything mode"""
        # Standard library imports
        import re

        base_args.score_everything_mode = True
        result = generate_output_filename(base_args)

        # Should match pattern: reports/YYYYMMDD_HHMMSS_matches_score-everything
        pattern = r"reports/\d{8}_\d{6}_matches_score-everything"
        assert re.match(pattern, result), f"Expected timestamp pattern, got: {result}"

    def test_timestamp_format_consistency(self, base_args):
        """Test that multiple calls produce properly formatted timestamps"""
        # Standard library imports
        import re
        import time

        # Get multiple filenames with 1 second delay to ensure different timestamps
        result1 = generate_output_filename(base_args)
        time.sleep(1.1)  # Sleep longer to ensure different second
        result2 = generate_output_filename(base_args)

        # Both should match the pattern
        pattern = r"reports/\d{8}_\d{6}_matches"
        assert re.match(pattern, result1)
        assert re.match(pattern, result2)

        # Timestamps should be different
        assert result1 != result2, f"Timestamps should be different: {result1} vs {result2}"
