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
        base_args.output_filename = "my_custom_analysis.csv"
        assert generate_output_filename(base_args) == "reports/my_custom_analysis"

        # Extension should be stripped regardless of format
        base_args.output_formats = ["xlsx"]
        base_args.output_filename = "my_custom_analysis.xlsx"
        assert generate_output_filename(base_args) == "reports/my_custom_analysis"

    def test_user_provided_filename_with_path_gets_correct_extension(self, base_args):
        """Test that user-provided filenames with paths get correct extension"""
        base_args.output_filename = "/path/to/my_analysis.csv"
        assert generate_output_filename(base_args) == "/path/to/my_analysis"

        # Extension should be stripped regardless of format
        base_args.output_formats = ["json"]
        base_args.output_filename = "/path/to/my_analysis.json"
        assert generate_output_filename(base_args) == "/path/to/my_analysis"

    def test_default_filename_no_filters(self, base_args):
        """Test default filename when no filters are applied"""
        assert generate_output_filename(base_args) == "reports/matches"

    def test_us_only_filter_adds_suffix(self, base_args):
        """Test that US-only filter adds us-only suffix"""
        base_args.us_only = True
        assert generate_output_filename(base_args) == "reports/matches_us-only"

    def test_year_range_filter(self, base_args):
        """Test filename generation with year range"""
        base_args.min_year = 1950
        base_args.max_year = 1960
        assert generate_output_filename(base_args) == "reports/matches_1950-1960"

    def test_single_year_filter(self, base_args):
        """Test filename generation when min_year equals max_year"""
        base_args.min_year = 1955
        base_args.max_year = 1955
        assert generate_output_filename(base_args) == "reports/matches_1955-1955"

    def test_min_year_only_filter(self, base_args):
        """Test filename generation with only minimum year"""
        base_args.min_year = 1945
        assert generate_output_filename(base_args) == "reports/matches_1945-current"

    def test_max_year_only_filter(self, base_args):
        """Test filename generation with only maximum year"""
        base_args.max_year = 1970
        assert generate_output_filename(base_args) == "reports/matches_pre-1970"

    def test_combined_us_only_and_year_range(self, base_args):
        """Test filename generation with both US-only and year range filters"""
        base_args.us_only = True
        base_args.min_year = 1950
        base_args.max_year = 1960
        assert generate_output_filename(base_args) == "reports/matches_us-only_1950-1960"

    def test_combined_us_only_and_single_year(self, base_args):
        """Test filename generation with US-only and single year"""
        base_args.us_only = True
        base_args.min_year = 1955
        base_args.max_year = 1955
        assert generate_output_filename(base_args) == "reports/matches_us-only_1955-1955"

    def test_combined_us_only_and_min_year(self, base_args):
        """Test filename generation with US-only and minimum year only"""
        base_args.us_only = True
        base_args.min_year = 1945
        assert generate_output_filename(base_args) == "reports/matches_us-only_1945-current"

    def test_combined_us_only_and_max_year(self, base_args):
        """Test filename generation with US-only and maximum year only"""
        base_args.us_only = True
        base_args.max_year = 1970
        assert generate_output_filename(base_args) == "reports/matches_us-only_pre-1970"

    def test_score_everything_indicator(self, base_args):
        """Test filename includes score-everything indicator when enabled"""
        base_args.score_everything_mode = True
        assert generate_output_filename(base_args) == "reports/matches_score-everything"

    def test_score_everything_with_filters(self, base_args):
        """Test filename with score-everything and other filters"""
        base_args.score_everything_mode = True
        base_args.us_only = True
        base_args.min_year = 1930
        base_args.max_year = 1960
        assert (
            generate_output_filename(base_args)
            == "reports/matches_us-only_1930-1960_score-everything"
        )


class TestFilenameEdgeCases:
    """Test edge cases and special scenarios"""

    def test_non_default_output_with_filters_gets_correct_extension(self):
        """Test that non-default output gets correct extension based on format"""
        args = Namespace(
            output_filename="custom.csv",
            us_only=True,
            min_year=1950,
            max_year=1960,
            score_everything_mode=False,
            output_formats=["csv"],
        )
        assert generate_output_filename(args) == "reports/custom"

        # Extension stripped regardless of format
        args.output_formats = ["xlsx"]
        assert generate_output_filename(args) == "reports/custom"

    def test_output_with_different_extension(self):
        """Test that file extensions are replaced based on output format"""
        args = Namespace(
            output_filename="data.tsv",
            us_only=True,
            min_year=1950,
            max_year=1960,
            score_everything_mode=False,
            output_formats=["csv"],
        )
        # Extension is stripped
        assert generate_output_filename(args) == "reports/data"

        # Test with xlsx format
        args.output_formats = ["xlsx"]
        assert generate_output_filename(args) == "reports/data"

    def test_relative_path_preserved(self):
        """Test that relative paths are preserved"""
        args = Namespace(
            output_filename="./results/analysis.csv",
            us_only=True,
            min_year=1950,
            max_year=None,
            score_everything_mode=False,
            output_formats=["csv"],
        )
        assert generate_output_filename(args) == "./results/analysis"

    def test_complex_filename_scenarios(self):
        """Test complex real-world scenarios"""
        # Scenario 1: Research focused on 1950s US publications
        args1 = Namespace(
            output_filename="matches.csv",
            us_only=True,
            min_year=1950,
            max_year=1959,
            score_everything_mode=False,
            output_formats=["csv"],
        )
        assert generate_output_filename(args1) == "reports/matches_us-only_1950-1959"

        # Scenario 2: Everything after 1930
        args2 = Namespace(
            output_filename="matches.csv",
            us_only=False,
            min_year=1930,
            max_year=None,
            score_everything_mode=False,
            output_formats=["csv"],
        )
        assert generate_output_filename(args2) == "reports/matches_1930-current"

        # Scenario 3: US publications up to 1970
        args3 = Namespace(
            output_filename="matches.csv",
            us_only=True,
            min_year=None,
            max_year=1970,
            score_everything_mode=False,
            output_formats=["csv"],
        )
        assert generate_output_filename(args3) == "reports/matches_us-only_pre-1970"

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
        assert "us-only" in generate_output_filename(args_default)

        # These should NOT trigger dynamic naming (different from default)
        args_similar = Namespace(
            output_filename="matches2.csv",
            us_only=True,
            min_year=1950,
            max_year=None,
            score_everything_mode=False,
            output_formats=["csv"],
        )
        assert generate_output_filename(args_similar) == "reports/matches2"

        # Test extension stripped
        args_similar.output_formats = ["json"]
        assert generate_output_filename(args_similar) == "reports/matches2"

        args_case = Namespace(
            output_filename="Matches.csv",
            us_only=True,
            min_year=1950,
            max_year=None,
            score_everything_mode=False,
            output_formats=["csv"],
        )
        assert generate_output_filename(args_case) == "reports/Matches"

        # Test case preservation
        args_case.output_formats = ["xlsx"]
        assert generate_output_filename(args_case) == "reports/Matches"

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
        assert generate_output_filename(args) == "reports/my_output"

        args.output_formats = ["xlsx"]
        assert generate_output_filename(args) == "reports/my_output"

        args.output_formats = ["json"]
        assert generate_output_filename(args) == "reports/my_output"
