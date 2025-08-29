# tests/adapters/cli/test_dynamic_filenames.py

"""Tests for dynamic filename generation functionality"""


# Standard library imports
from argparse import Namespace
from re import match

# Third party imports
from pytest import fixture

# Local imports
# Local imports - import CLI functions from new location
from marc_pd_tool.adapters.cli import generate_output_filename


def create_test_args(**kwargs):
    """Helper to create test Namespace with all required attributes"""
    # Local imports
    from marc_pd_tool.infrastructure.config import get_config

    config = get_config()

    # Set defaults for all required attributes
    defaults = {
        "output_filename": "matches.csv",
        "us_only": False,
        "min_year": None,
        "max_year": None,
        "score_everything_mode": False,
        "score_everything": False,
        "ground_truth_mode": None,
        "output_formats": ["csv"],
        "title_threshold": config.get_threshold("title"),
        "author_threshold": config.get_threshold("author"),
        "publisher_threshold": config.get_threshold("publisher"),
    }

    # Update with provided kwargs
    defaults.update(kwargs)

    return Namespace(**defaults)


class TestDynamicFilenames:
    """Test dynamic filename generation functionality"""

    @fixture
    def base_args(self):
        """Create base args namespace for testing"""
        return create_test_args()

    def test_user_provided_filename_gets_correct_extension(self, base_args):
        """Test that user-provided filenames get extensions stripped (added by exporters)"""

        base_args.output_filename = "my_custom_analysis.csv"
        result = generate_output_filename(base_args)
        pattern = r"reports/\d{8}_\d{6}_my_custom_analysis"
        assert match(pattern, result), f"Expected timestamp pattern, got: {result}"

        # Extension should be stripped regardless of format
        base_args.output_formats = ["xlsx"]
        base_args.output_filename = "my_custom_analysis.xlsx"
        result = generate_output_filename(base_args)
        pattern = r"reports/\d{8}_\d{6}_my_custom_analysis"
        assert match(pattern, result), f"Expected timestamp pattern, got: {result}"

    def test_user_provided_filename_with_path_gets_correct_extension(self, base_args):
        """Test that user-provided filenames with paths get correct extension"""

        base_args.output_filename = "/path/to/my_analysis.csv"
        result = generate_output_filename(base_args)
        pattern = r"/path/to/\d{8}_\d{6}_my_analysis"
        assert match(pattern, result), f"Expected timestamp pattern, got: {result}"

        # Extension should be stripped regardless of format
        base_args.output_formats = ["json"]
        base_args.output_filename = "/path/to/my_analysis.json"
        result = generate_output_filename(base_args)
        pattern = r"/path/to/\d{8}_\d{6}_my_analysis"
        assert match(pattern, result), f"Expected timestamp pattern, got: {result}"

    def test_default_filename_no_filters(self, base_args):
        """Test default filename when no filters are applied"""

        result = generate_output_filename(base_args)
        pattern = r"reports/\d{8}_\d{6}_matches"
        assert match(pattern, result), f"Expected timestamp pattern, got: {result}"

    def test_us_only_filter_adds_suffix(self, base_args):
        """Test that US-only filter adds us suffix"""

        base_args.us_only = True
        result = generate_output_filename(base_args)
        pattern = r"reports/\d{8}_\d{6}_matches_us"
        assert match(pattern, result), f"Expected timestamp pattern, got: {result}"

    def test_year_range_filter(self, base_args):
        """Test filename generation with year range"""

        base_args.min_year = 1950
        base_args.max_year = 1960
        result = generate_output_filename(base_args)
        pattern = r"reports/\d{8}_\d{6}_matches_y1950-1960"
        assert match(pattern, result), f"Expected timestamp pattern, got: {result}"

    def test_single_year_filter(self, base_args):
        """Test filename generation when min_year equals max_year"""

        base_args.min_year = 1955
        base_args.max_year = 1955
        result = generate_output_filename(base_args)
        pattern = r"reports/\d{8}_\d{6}_matches_y1955-1955"
        assert match(pattern, result), f"Expected timestamp pattern, got: {result}"

    def test_min_year_only_filter(self, base_args):
        """Test filename generation with only minimum year"""

        base_args.min_year = 1945
        result = generate_output_filename(base_args)
        pattern = r"reports/\d{8}_\d{6}_matches_y1945-9999"
        assert match(pattern, result), f"Expected timestamp pattern, got: {result}"

    def test_max_year_only_filter(self, base_args):
        """Test filename generation with only maximum year"""

        base_args.max_year = 1970
        result = generate_output_filename(base_args)
        pattern = r"reports/\d{8}_\d{6}_matches_y0-1970"
        assert match(pattern, result), f"Expected timestamp pattern, got: {result}"

    def test_combined_us_only_and_year_range(self, base_args):
        """Test filename generation with both US-only and year range filters"""

        base_args.us_only = True
        base_args.min_year = 1950
        base_args.max_year = 1960
        result = generate_output_filename(base_args)
        pattern = r"reports/\d{8}_\d{6}_matches_y1950-1960_us"
        assert match(pattern, result), f"Expected timestamp pattern, got: {result}"

    def test_combined_us_only_and_single_year(self, base_args):
        """Test filename generation with US-only and single year"""

        base_args.us_only = True
        base_args.min_year = 1955
        base_args.max_year = 1955
        result = generate_output_filename(base_args)
        pattern = r"reports/\d{8}_\d{6}_matches_y1955-1955_us"
        assert match(pattern, result), f"Expected timestamp pattern, got: {result}"

    def test_combined_us_only_and_min_year(self, base_args):
        """Test filename generation with US-only and minimum year only"""

        base_args.us_only = True
        base_args.min_year = 1945
        result = generate_output_filename(base_args)
        pattern = r"reports/\d{8}_\d{6}_matches_y1945-9999_us"
        assert match(pattern, result), f"Expected timestamp pattern, got: {result}"

    def test_combined_us_only_and_max_year(self, base_args):
        """Test filename generation with US-only and maximum year only"""

        base_args.us_only = True
        base_args.max_year = 1970
        result = generate_output_filename(base_args)
        pattern = r"reports/\d{8}_\d{6}_matches_y0-1970_us"
        assert match(pattern, result), f"Expected timestamp pattern, got: {result}"

    def test_score_everything_indicator(self, base_args):
        """Test filename includes all indicator when enabled"""

        base_args.score_everything = True
        result = generate_output_filename(base_args)
        pattern = r"reports/\d{8}_\d{6}_matches_all"
        assert match(pattern, result), f"Expected timestamp pattern, got: {result}"

    def test_score_everything_with_filters(self, base_args):
        """Test filename with all and other filters"""

        base_args.score_everything = True
        base_args.us_only = True
        base_args.min_year = 1930
        base_args.max_year = 1960
        result = generate_output_filename(base_args)
        pattern = r"reports/\d{8}_\d{6}_matches_y1930-1960_us_all"
        assert match(pattern, result), f"Expected timestamp pattern, got: {result}"


class TestFilenameEdgeCases:
    """Test edge cases and special scenarios"""

    def test_non_default_output_with_filters_gets_correct_extension(self):
        """Test that non-default output gets correct extension based on format"""

        args = create_test_args(
            output_filename="custom.csv",
            us_only=True,
            min_year=1950,
            max_year=1960,
            score_everything_mode=False,
            output_formats=["csv"],
        )
        result = generate_output_filename(args)
        pattern = r"reports/\d{8}_\d{6}_custom"
        assert match(pattern, result), f"Expected timestamp pattern, got: {result}"

        # Extension stripped regardless of format
        args.output_formats = ["xlsx"]
        result = generate_output_filename(args)
        assert match(pattern, result), f"Expected timestamp pattern, got: {result}"

    def test_output_with_different_extension(self):
        """Test that file extensions are replaced based on output format"""

        args = create_test_args(
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
        assert match(pattern, result), f"Expected timestamp pattern, got: {result}"

        # Test with xlsx format
        args.output_formats = ["xlsx"]
        result = generate_output_filename(args)
        assert match(pattern, result), f"Expected timestamp pattern, got: {result}"

    def test_relative_path_preserved(self):
        """Test that relative paths are preserved"""

        args = create_test_args(
            output_filename="./results/analysis.csv",
            us_only=True,
            min_year=1950,
            max_year=None,
            score_everything_mode=False,
            output_formats=["csv"],
        )
        result = generate_output_filename(args)
        pattern = r"\./results/\d{8}_\d{6}_analysis"
        assert match(pattern, result), f"Expected timestamp pattern, got: {result}"

    def test_complex_filename_scenarios(self):
        """Test complex real-world scenarios"""

        # Scenario 1: Research focused on 1950s US publications
        args1 = create_test_args(
            output_filename="matches.csv",
            us_only=True,
            min_year=1950,
            max_year=1959,
            score_everything_mode=False,
            output_formats=["csv"],
        )
        result1 = generate_output_filename(args1)
        pattern1 = r"reports/\d{8}_\d{6}_matches_y1950-1959_us"
        assert match(pattern1, result1), f"Expected timestamp pattern, got: {result1}"

        # Scenario 2: Everything after 1930
        args2 = create_test_args(
            output_filename="matches.csv",
            us_only=False,
            min_year=1930,
            max_year=None,
            score_everything_mode=False,
            output_formats=["csv"],
        )
        result2 = generate_output_filename(args2)
        pattern2 = r"reports/\d{8}_\d{6}_matches_y1930-9999"
        assert match(pattern2, result2), f"Expected timestamp pattern, got: {result2}"

        # Scenario 3: US publications up to 1970
        args3 = create_test_args(
            output_filename="matches.csv",
            us_only=True,
            min_year=None,
            max_year=1970,
            score_everything_mode=False,
            output_formats=["csv"],
        )
        result3 = generate_output_filename(args3)
        pattern3 = r"reports/\d{8}_\d{6}_matches_y0-1970_us"
        assert match(pattern3, result3), f"Expected timestamp pattern, got: {result3}"

    def test_default_detection_logic(self):
        """Test that only the exact default triggers dynamic naming"""
        # These should trigger dynamic naming
        args_default = create_test_args(
            output_filename="matches.csv",
            us_only=True,
            min_year=1950,
            max_year=None,
            score_everything_mode=False,
            output_formats=["csv"],
        )
        result = generate_output_filename(args_default)
        assert "us" in result

        # These should NOT trigger dynamic naming (different from default)
        args_similar = create_test_args(
            output_filename="matches2.csv",
            us_only=True,
            min_year=1950,
            max_year=None,
            score_everything_mode=False,
            output_formats=["csv"],
        )

        result = generate_output_filename(args_similar)
        pattern = r"reports/\d{8}_\d{6}_matches2"
        assert match(pattern, result), f"Expected timestamp pattern, got: {result}"

        # Test extension stripped
        args_similar.output_formats = ["json"]
        result = generate_output_filename(args_similar)
        assert match(pattern, result), f"Expected timestamp pattern, got: {result}"

        args_case = create_test_args(
            output_filename="Matches.csv",
            us_only=True,
            min_year=1950,
            max_year=None,
            score_everything_mode=False,
            output_formats=["csv"],
        )

        result = generate_output_filename(args_case)
        pattern = r"reports/\d{8}_\d{6}_Matches"
        assert match(pattern, result), f"Expected timestamp pattern, got: {result}"

        # Test case preservation
        args_case.output_formats = ["xlsx"]
        result = generate_output_filename(args_case)
        assert match(pattern, result), f"Expected timestamp pattern, got: {result}"

    def test_filename_without_extension_gets_added(self):
        """Test that filenames without extensions get the correct extension added"""
        args = create_test_args(
            output_filename="my_output",
            us_only=False,
            min_year=None,
            max_year=None,
            score_everything_mode=False,
            output_formats=["csv"],
        )

        result = generate_output_filename(args)
        pattern = r"reports/\d{8}_\d{6}_my_output"
        assert match(pattern, result), f"Expected timestamp pattern, got: {result}"

        args.output_formats = ["xlsx"]
        result = generate_output_filename(args)
        assert match(pattern, result), f"Expected timestamp pattern, got: {result}"

        args.output_formats = ["json"]
        result = generate_output_filename(args)
        assert match(pattern, result), f"Expected timestamp pattern, got: {result}"


class TestTimestampedFilenames:
    """Test that all filenames get timestamp prefixes"""

    @fixture
    def base_args(self):
        """Create base args namespace for testing"""
        return create_test_args(
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

        result = generate_output_filename(base_args)

        # Should match pattern: reports/YYYYMMDD_HHMMSS_matches
        pattern = r"reports/\d{8}_\d{6}_matches"
        assert match(pattern, result), f"Expected timestamp pattern, got: {result}"

        # Verify timestamp is recent (within last minute)
        timestamp_part = result.split("/")[1].split("_matches")[0]
        timestamp_str = timestamp_part.replace("_", "")
        timestamp_dt = datetime.strptime(timestamp_str, "%Y%m%d%H%M%S")
        now = datetime.now()
        time_diff = (now - timestamp_dt).total_seconds()
        assert time_diff < 60, f"Timestamp not recent: {timestamp_dt}"

    def test_user_provided_filename_gets_timestamp(self, base_args):
        """Test that user-provided filename gets timestamp prefix"""

        base_args.output_filename = "custom_output.csv"
        result = generate_output_filename(base_args)

        # Should match pattern: reports/YYYYMMDD_HHMMSS_custom_output
        pattern = r"reports/\d{8}_\d{6}_custom_output"
        assert match(pattern, result), f"Expected timestamp pattern, got: {result}"

    def test_path_with_directory_preserves_directory(self, base_args):
        """Test that directory path is preserved and timestamp only added to filename"""

        base_args.output_filename = "/custom/path/output.csv"
        result = generate_output_filename(base_args)

        # Should match pattern: /custom/path/YYYYMMDD_HHMMSS_output
        pattern = r"/custom/path/\d{8}_\d{6}_output"
        assert match(pattern, result), f"Expected timestamp pattern, got: {result}"

    def test_timestamp_with_filters(self, base_args):
        """Test that timestamp works with various filters"""

        base_args.us_only = True
        base_args.min_year = 1950
        base_args.max_year = 1970
        result = generate_output_filename(base_args)

        # Should match pattern: reports/YYYYMMDD_HHMMSS_matches_y1950-1970_us
        pattern = r"reports/\d{8}_\d{6}_matches_y1950-1970_us"
        assert match(pattern, result), f"Expected timestamp pattern, got: {result}"

    def test_timestamp_with_ground_truth_mode(self, base_args):
        """Test that timestamp works with ground truth mode"""

        base_args.ground_truth_mode = True  # Ground truth mode flag
        result = generate_output_filename(base_args)

        # Should match pattern: reports/YYYYMMDD_HHMMSS_matches_gt
        pattern = r"reports/\d{8}_\d{6}_matches_gt"
        assert match(pattern, result), f"Expected timestamp pattern, got: {result}"

    def test_timestamp_with_score_everything(self, base_args):
        """Test that timestamp works with all mode"""

        base_args.score_everything = True
        result = generate_output_filename(base_args)

        # Should match pattern: reports/YYYYMMDD_HHMMSS_matches_all
        pattern = r"reports/\d{8}_\d{6}_matches_all"
        assert match(pattern, result), f"Expected timestamp pattern, got: {result}"

    def test_timestamp_format_consistency(self, base_args):
        """Test that multiple calls produce properly formatted timestamps"""

        # Standard library imports
        import time

        # Get multiple filenames with 1 second delay to ensure different timestamps
        result1 = generate_output_filename(base_args)
        time.sleep(1.1)  # Sleep longer to ensure different second
        result2 = generate_output_filename(base_args)

        # Both should match the pattern
        pattern = r"reports/\d{8}_\d{6}_matches"
        assert match(pattern, result1)
        assert match(pattern, result2)

        # Timestamps should be different
        assert result1 != result2, f"Timestamps should be different: {result1} vs {result2}"
