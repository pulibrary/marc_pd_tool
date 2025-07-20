"""Tests for dynamic filename generation functionality"""

# Standard library imports
from argparse import Namespace
from pathlib import Path

# Local imports - need to import from compare.py
import sys

# Third party imports
# Third-party imports
from pytest import fixture

sys.path.insert(0, str(Path(__file__).parent.parent))
# Local imports
from compare import build_year_part
from compare import generate_output_filename


class TestDynamicFilenames:
    """Test dynamic filename generation functionality"""

    @fixture
    def base_args(self):
        """Create base args namespace for testing"""
        return Namespace(
            output="matches.csv", us_only=False, min_year=None, max_year=None  # Default value
        )

    def test_user_provided_filename_unchanged(self, base_args):
        """Test that user-provided filenames are not modified"""
        base_args.output = "my_custom_analysis.csv"
        assert generate_output_filename(base_args) == "my_custom_analysis.csv"

    def test_user_provided_filename_with_path_unchanged(self, base_args):
        """Test that user-provided filenames with paths are not modified"""
        base_args.output = "/path/to/my_analysis.csv"
        assert generate_output_filename(base_args) == "/path/to/my_analysis.csv"

    def test_default_filename_no_filters(self, base_args):
        """Test default filename when no filters are applied"""
        assert generate_output_filename(base_args) == "matches.csv"

    def test_us_only_filter_adds_suffix(self, base_args):
        """Test that US-only filter adds us-only suffix"""
        base_args.us_only = True
        assert generate_output_filename(base_args) == "matches_us-only.csv"

    def test_year_range_filter(self, base_args):
        """Test filename generation with year range"""
        base_args.min_year = 1950
        base_args.max_year = 1960
        assert generate_output_filename(base_args) == "matches_1950-1960.csv"

    def test_single_year_filter(self, base_args):
        """Test filename generation when min_year equals max_year"""
        base_args.min_year = 1955
        base_args.max_year = 1955
        assert generate_output_filename(base_args) == "matches_1955-only.csv"

    def test_min_year_only_filter(self, base_args):
        """Test filename generation with only minimum year"""
        base_args.min_year = 1945
        assert generate_output_filename(base_args) == "matches_after-1945.csv"

    def test_max_year_only_filter(self, base_args):
        """Test filename generation with only maximum year"""
        base_args.max_year = 1970
        assert generate_output_filename(base_args) == "matches_before-1970.csv"

    def test_combined_us_only_and_year_range(self, base_args):
        """Test filename generation with both US-only and year range filters"""
        base_args.us_only = True
        base_args.min_year = 1950
        base_args.max_year = 1960
        assert generate_output_filename(base_args) == "matches_us-only_1950-1960.csv"

    def test_combined_us_only_and_single_year(self, base_args):
        """Test filename generation with US-only and single year"""
        base_args.us_only = True
        base_args.min_year = 1955
        base_args.max_year = 1955
        assert generate_output_filename(base_args) == "matches_us-only_1955-only.csv"

    def test_combined_us_only_and_min_year(self, base_args):
        """Test filename generation with US-only and minimum year only"""
        base_args.us_only = True
        base_args.min_year = 1945
        assert generate_output_filename(base_args) == "matches_us-only_after-1945.csv"

    def test_combined_us_only_and_max_year(self, base_args):
        """Test filename generation with US-only and maximum year only"""
        base_args.us_only = True
        base_args.max_year = 1970
        assert generate_output_filename(base_args) == "matches_us-only_before-1970.csv"


class TestBuildYearPart:
    """Test year part generation for filenames"""

    def test_year_range(self):
        """Test year range formatting"""
        assert build_year_part(1950, 1960) == "1950-1960"

    def test_single_year(self):
        """Test single year formatting"""
        assert build_year_part(1955, 1955) == "1955-only"

    def test_min_year_only(self):
        """Test minimum year only formatting"""
        assert build_year_part(1945, None) == "after-1945"

    def test_max_year_only(self):
        """Test maximum year only formatting"""
        assert build_year_part(None, 1970) == "before-1970"

    def test_no_years(self):
        """Test no year constraints"""
        assert build_year_part(None, None) is None

    def test_wide_year_range(self):
        """Test wide year range formatting"""
        assert build_year_part(1900, 2000) == "1900-2000"

    def test_edge_year_values(self):
        """Test edge year values"""
        assert build_year_part(1, 9999) == "1-9999"
        assert build_year_part(2023, 2023) == "2023-only"


class TestFilenameEdgeCases:
    """Test edge cases and special scenarios"""

    def test_non_default_output_with_filters_unchanged(self):
        """Test that non-default output is unchanged even with filters"""
        args = Namespace(output="custom.csv", us_only=True, min_year=1950, max_year=1960)
        assert generate_output_filename(args) == "custom.csv"

    def test_output_with_different_extension(self):
        """Test that different file extensions are preserved"""
        args = Namespace(output="data.tsv", us_only=True, min_year=1950, max_year=1960)
        assert generate_output_filename(args) == "data.tsv"

    def test_relative_path_preserved(self):
        """Test that relative paths are preserved"""
        args = Namespace(
            output="./results/analysis.csv", us_only=True, min_year=1950, max_year=None
        )
        assert generate_output_filename(args) == "./results/analysis.csv"

    def test_complex_filename_scenarios(self):
        """Test complex real-world scenarios"""
        # Scenario 1: Research focused on 1950s US publications
        args1 = Namespace(output="matches.csv", us_only=True, min_year=1950, max_year=1959)
        assert generate_output_filename(args1) == "matches_us-only_1950-1959.csv"

        # Scenario 2: Everything after 1930
        args2 = Namespace(output="matches.csv", us_only=False, min_year=1930, max_year=None)
        assert generate_output_filename(args2) == "matches_after-1930.csv"

        # Scenario 3: US publications up to 1970
        args3 = Namespace(output="matches.csv", us_only=True, min_year=None, max_year=1970)
        assert generate_output_filename(args3) == "matches_us-only_before-1970.csv"

    def test_default_detection_logic(self):
        """Test that only the exact default triggers dynamic naming"""
        # These should trigger dynamic naming
        args_default = Namespace(output="matches.csv", us_only=True, min_year=1950, max_year=None)
        assert "us-only" in generate_output_filename(args_default)

        # These should NOT trigger dynamic naming (different from default)
        args_similar = Namespace(output="matches2.csv", us_only=True, min_year=1950, max_year=None)
        assert generate_output_filename(args_similar) == "matches2.csv"

        args_case = Namespace(output="Matches.csv", us_only=True, min_year=1950, max_year=None)
        assert generate_output_filename(args_case) == "Matches.csv"
