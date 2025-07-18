"""Tests for year filtering functionality in MARC extraction"""

# Standard library imports
from pathlib import Path

# Local imports
from marc_pd_tool.enums import AuthorType
from marc_pd_tool.enums import CountryClassification
from marc_pd_tool.marc_extractor import ParallelMarcExtractor
from marc_pd_tool.publication import Publication

# pytest imported automatically by test runner


class TestYearFiltering:
    """Test year filtering functionality"""

    def test_should_include_record_no_filters(self):
        """Test that all records are included when no year filters are set"""
        extractor = ParallelMarcExtractor("dummy_path")

        # Create test publications with different years
        pub_1940 = Publication(
            "Test 1940",
            pub_date="1940",
            author_type=AuthorType.PERSONAL,
            country_classification=CountryClassification.US,
        )
        pub_1955 = Publication(
            "Test 1955",
            pub_date="1955",
            author_type=AuthorType.PERSONAL,
            country_classification=CountryClassification.US,
        )
        pub_2020 = Publication(
            "Test 2020",
            pub_date="2020",
            author_type=AuthorType.PERSONAL,
            country_classification=CountryClassification.US,
        )
        pub_no_year = Publication(
            "Test No Year",
            author_type=AuthorType.PERSONAL,
            country_classification=CountryClassification.US,
        )

        # All should be included when no filters are set
        assert extractor._should_include_record(pub_1940) is True
        assert extractor._should_include_record(pub_1955) is True
        assert extractor._should_include_record(pub_2020) is True
        assert extractor._should_include_record(pub_no_year) is True

    def test_should_include_record_min_year_only(self):
        """Test filtering with only minimum year set"""
        extractor = ParallelMarcExtractor("dummy_path", min_year=1950)

        pub_1940 = Publication(
            "Test 1940",
            pub_date="1940",
            author_type=AuthorType.PERSONAL,
            country_classification=CountryClassification.US,
        )
        pub_1950 = Publication(
            "Test 1950",
            pub_date="1950",
            author_type=AuthorType.PERSONAL,
            country_classification=CountryClassification.US,
        )
        pub_1960 = Publication(
            "Test 1960",
            pub_date="1960",
            author_type=AuthorType.PERSONAL,
            country_classification=CountryClassification.US,
        )

        assert extractor._should_include_record(pub_1940) is False  # Too old
        assert extractor._should_include_record(pub_1950) is True  # Exactly min year
        assert extractor._should_include_record(pub_1960) is True  # After min year

    def test_should_include_record_max_year_only(self):
        """Test filtering with only maximum year set"""
        extractor = ParallelMarcExtractor("dummy_path", max_year=1960)

        pub_1940 = Publication(
            "Test 1940",
            pub_date="1940",
            author_type=AuthorType.PERSONAL,
            country_classification=CountryClassification.US,
        )
        pub_1960 = Publication(
            "Test 1960",
            pub_date="1960",
            author_type=AuthorType.PERSONAL,
            country_classification=CountryClassification.US,
        )
        pub_1970 = Publication(
            "Test 1970",
            pub_date="1970",
            author_type=AuthorType.PERSONAL,
            country_classification=CountryClassification.US,
        )

        assert extractor._should_include_record(pub_1940) is True  # Before max year
        assert extractor._should_include_record(pub_1960) is True  # Exactly max year
        assert extractor._should_include_record(pub_1970) is False  # Too new

    def test_should_include_record_year_range(self):
        """Test filtering with both min and max year set (year range)"""
        extractor = ParallelMarcExtractor("dummy_path", min_year=1950, max_year=1960)

        pub_1940 = Publication(
            "Test 1940",
            pub_date="1940",
            author_type=AuthorType.PERSONAL,
            country_classification=CountryClassification.US,
        )
        pub_1950 = Publication(
            "Test 1950",
            pub_date="1950",
            author_type=AuthorType.PERSONAL,
            country_classification=CountryClassification.US,
        )
        pub_1955 = Publication(
            "Test 1955",
            pub_date="1955",
            author_type=AuthorType.PERSONAL,
            country_classification=CountryClassification.US,
        )
        pub_1960 = Publication(
            "Test 1960",
            pub_date="1960",
            author_type=AuthorType.PERSONAL,
            country_classification=CountryClassification.US,
        )
        pub_1970 = Publication(
            "Test 1970",
            pub_date="1970",
            author_type=AuthorType.PERSONAL,
            country_classification=CountryClassification.US,
        )

        assert extractor._should_include_record(pub_1940) is False  # Too old
        assert extractor._should_include_record(pub_1950) is True  # Exactly min year
        assert extractor._should_include_record(pub_1955) is True  # In range
        assert extractor._should_include_record(pub_1960) is True  # Exactly max year
        assert extractor._should_include_record(pub_1970) is False  # Too new

    def test_should_include_record_single_year(self):
        """Test filtering to a single year (min_year == max_year)"""
        extractor = ParallelMarcExtractor("dummy_path", min_year=1955, max_year=1955)

        pub_1954 = Publication(
            "Test 1954",
            pub_date="1954",
            author_type=AuthorType.PERSONAL,
            country_classification=CountryClassification.US,
        )
        pub_1955 = Publication(
            "Test 1955",
            pub_date="1955",
            author_type=AuthorType.PERSONAL,
            country_classification=CountryClassification.US,
        )
        pub_1956 = Publication(
            "Test 1956",
            pub_date="1956",
            author_type=AuthorType.PERSONAL,
            country_classification=CountryClassification.US,
        )

        assert extractor._should_include_record(pub_1954) is False  # Before target year
        assert extractor._should_include_record(pub_1955) is True  # Exactly target year
        assert extractor._should_include_record(pub_1956) is False  # After target year

    def test_should_include_record_no_year_always_included(self):
        """Test that records without publication years are always included"""
        extractor_min = ParallelMarcExtractor("dummy_path", min_year=1950)
        extractor_max = ParallelMarcExtractor("dummy_path", max_year=1960)
        extractor_range = ParallelMarcExtractor("dummy_path", min_year=1950, max_year=1960)

        pub_no_year = Publication(
            "Test No Year",
            author_type=AuthorType.PERSONAL,
            country_classification=CountryClassification.US,
        )

        # Records without years should always be included regardless of filters
        assert extractor_min._should_include_record(pub_no_year) is True
        assert extractor_max._should_include_record(pub_no_year) is True
        assert extractor_range._should_include_record(pub_no_year) is True

    def test_extractor_constructor_accepts_max_year(self):
        """Test that ParallelMarcExtractor constructor accepts max_year parameter"""
        # Test with min_year only
        extractor1 = ParallelMarcExtractor("dummy_path", min_year=1950)
        assert extractor1.min_year == 1950
        assert extractor1.max_year is None

        # Test with max_year only
        extractor2 = ParallelMarcExtractor("dummy_path", max_year=1960)
        assert extractor2.min_year is None
        assert extractor2.max_year == 1960

        # Test with both min_year and max_year
        extractor3 = ParallelMarcExtractor("dummy_path", min_year=1950, max_year=1960)
        assert extractor3.min_year == 1950
        assert extractor3.max_year == 1960

        # Test with neither
        extractor4 = ParallelMarcExtractor("dummy_path")
        assert extractor4.min_year is None
        assert extractor4.max_year is None

    def test_year_boundary_conditions(self):
        """Test boundary conditions for year filtering"""
        extractor = ParallelMarcExtractor("dummy_path", min_year=1950, max_year=1960)

        # Test exact boundaries
        pub_min_boundary = Publication(
            "Test Min Boundary",
            pub_date="1950",
            author_type=AuthorType.PERSONAL,
            country_classification=CountryClassification.US,
        )
        pub_max_boundary = Publication(
            "Test Max Boundary",
            pub_date="1960",
            author_type=AuthorType.PERSONAL,
            country_classification=CountryClassification.US,
        )

        # Boundary values should be included (inclusive range)
        assert extractor._should_include_record(pub_min_boundary) is True
        assert extractor._should_include_record(pub_max_boundary) is True

        # Just outside boundaries should be excluded
        pub_below_min = Publication(
            "Test Below Min",
            pub_date="1949",
            author_type=AuthorType.PERSONAL,
            country_classification=CountryClassification.US,
        )
        pub_above_max = Publication(
            "Test Above Max",
            pub_date="1961",
            author_type=AuthorType.PERSONAL,
            country_classification=CountryClassification.US,
        )

        assert extractor._should_include_record(pub_below_min) is False
        assert extractor._should_include_record(pub_above_max) is False

    def test_year_filtering_with_various_date_formats(self):
        """Test year filtering works with different publication date formats"""
        extractor = ParallelMarcExtractor("dummy_path", min_year=1950, max_year=1960)

        # Test different date formats that should all extract to year 1955
        pub_year_only = Publication(
            "Test Year Only",
            pub_date="1955",
            author_type=AuthorType.PERSONAL,
            country_classification=CountryClassification.US,
        )
        pub_full_date = Publication(
            "Test Full Date",
            pub_date="1955-06-15",
            author_type=AuthorType.PERSONAL,
            country_classification=CountryClassification.US,
        )
        pub_complex_date = Publication(
            "Test Complex Date",
            pub_date="c1955",
            author_type=AuthorType.PERSONAL,
            country_classification=CountryClassification.US,
        )

        # All should be included as they're in the 1950-1960 range
        assert extractor._should_include_record(pub_year_only) is True
        assert extractor._should_include_record(pub_full_date) is True
        assert extractor._should_include_record(pub_complex_date) is True

    def test_command_line_help_includes_max_year(self):
        """Test that command line help includes max-year option"""
        # Standard library imports
        import subprocess

        result = subprocess.run(
            ["pdm", "run", "python", "compare.py", "--help"],
            capture_output=True,
            text=True,
            cwd="/Users/jstroop/workspace/marc_pd_tool",
        )

        assert "--max-year" in result.stdout
        assert "Maximum publication year to include" in result.stdout
