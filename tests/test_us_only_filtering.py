"""Tests for US-only filtering functionality"""

# Standard library imports
from argparse import ArgumentParser
from tempfile import NamedTemporaryFile
from os import unlink

# Third-party imports
from pytest import fixture

# Local imports
from marc_pd_tool.enums import CountryClassification, AuthorType
from marc_pd_tool.marc_extractor import ParallelMarcExtractor
from marc_pd_tool.publication import Publication


class TestUSOnlyFiltering:
    """Test US-only filtering functionality"""

    @fixture
    def us_publication(self):
        """Create a US publication for testing"""
        return Publication(
            title="Test US Book",
            author="US Author",
            pub_date="1950",
            source_id="us_001",
            country_classification=CountryClassification.US,
            author_type=AuthorType.PERSONAL,
        )

    @fixture
    def non_us_publication(self):
        """Create a non-US publication for testing"""
        return Publication(
            title="Test Foreign Book",
            author="Foreign Author", 
            pub_date="1950",
            source_id="non_us_001",
            country_classification=CountryClassification.NON_US,
            author_type=AuthorType.PERSONAL,
        )

    @fixture
    def unknown_country_publication(self):
        """Create a publication with unknown country for testing"""
        return Publication(
            title="Test Unknown Book",
            author="Unknown Author",
            pub_date="1950", 
            source_id="unknown_001",
            country_classification=CountryClassification.UNKNOWN,
            author_type=AuthorType.PERSONAL,
        )

    def test_us_only_filter_includes_us_records(self, us_publication):
        """Test that US-only filter includes US records"""
        extractor = ParallelMarcExtractor("dummy.xml", us_only=True)
        assert extractor._should_include_record(us_publication) is True

    def test_us_only_filter_excludes_non_us_records(self, non_us_publication):
        """Test that US-only filter excludes non-US records"""
        extractor = ParallelMarcExtractor("dummy.xml", us_only=True)
        assert extractor._should_include_record(non_us_publication) is False

    def test_us_only_filter_excludes_unknown_country_records(self, unknown_country_publication):
        """Test that US-only filter excludes unknown country records"""
        extractor = ParallelMarcExtractor("dummy.xml", us_only=True)
        assert extractor._should_include_record(unknown_country_publication) is False

    def test_us_only_false_includes_all_countries(self, us_publication, non_us_publication, unknown_country_publication):
        """Test that us_only=False includes all country classifications"""
        extractor = ParallelMarcExtractor("dummy.xml", us_only=False)
        assert extractor._should_include_record(us_publication) is True
        assert extractor._should_include_record(non_us_publication) is True
        assert extractor._should_include_record(unknown_country_publication) is True

    def test_us_only_with_year_filtering(self):
        """Test that US-only filter works with year filtering"""
        # Create US publication that should be filtered by year
        old_us_pub = Publication(
            title="Old US Book",
            author="US Author",
            pub_date="1920",
            source_id="old_us_001",
            country_classification=CountryClassification.US,
            author_type=AuthorType.PERSONAL,
        )
        old_us_pub.year = 1920

        # Create non-US publication that should be filtered by country
        new_non_us_pub = Publication(
            title="New Foreign Book", 
            author="Foreign Author",
            pub_date="1950",
            source_id="new_non_us_001",
            country_classification=CountryClassification.NON_US,
            author_type=AuthorType.PERSONAL,
        )
        new_non_us_pub.year = 1950

        # Create US publication that should pass both filters
        new_us_pub = Publication(
            title="New US Book",
            author="US Author",
            pub_date="1950", 
            source_id="new_us_001",
            country_classification=CountryClassification.US,
            author_type=AuthorType.PERSONAL,
        )
        new_us_pub.year = 1950

        extractor = ParallelMarcExtractor("dummy.xml", min_year=1930, us_only=True)
        
        # Old US publication filtered by year
        assert extractor._should_include_record(old_us_pub) is False
        # Non-US publication filtered by country
        assert extractor._should_include_record(new_non_us_pub) is False
        # US publication passes both filters
        assert extractor._should_include_record(new_us_pub) is True

    def test_us_only_with_no_year(self):
        """Test that US-only filter handles publications with no year"""
        us_pub_no_year = Publication(
            title="US Book No Year",
            author="US Author", 
            pub_date="",
            source_id="us_no_year_001",
            country_classification=CountryClassification.US,
            author_type=AuthorType.PERSONAL,
        )
        us_pub_no_year.year = None

        non_us_pub_no_year = Publication(
            title="Foreign Book No Year",
            author="Foreign Author",
            pub_date="",
            source_id="non_us_no_year_001", 
            country_classification=CountryClassification.NON_US,
            author_type=AuthorType.PERSONAL,
        )
        non_us_pub_no_year.year = None

        extractor = ParallelMarcExtractor("dummy.xml", us_only=True)
        
        # US publication with no year should be included
        assert extractor._should_include_record(us_pub_no_year) is True
        # Non-US publication with no year should be excluded
        assert extractor._should_include_record(non_us_pub_no_year) is False

    def test_command_line_argument_parsing(self):
        """Test that --us-only command line argument is parsed correctly"""
        # Test without --us-only flag
        parser = ArgumentParser()
        parser.add_argument("--us-only", action="store_true", help="Test flag")
        
        args_no_flag = parser.parse_args([])
        assert args_no_flag.us_only is False
        
        # Test with --us-only flag
        args_with_flag = parser.parse_args(["--us-only"])
        assert args_with_flag.us_only is True

    def test_extractor_constructor_accepts_us_only_parameter(self):
        """Test that ParallelMarcExtractor accepts us_only parameter"""
        # Test default value
        extractor_default = ParallelMarcExtractor("dummy.xml")
        assert extractor_default.us_only is False
        
        # Test explicit False
        extractor_false = ParallelMarcExtractor("dummy.xml", us_only=False)
        assert extractor_false.us_only is False
        
        # Test explicit True
        extractor_true = ParallelMarcExtractor("dummy.xml", us_only=True)
        assert extractor_true.us_only is True

    def test_us_only_filter_edge_cases(self):
        """Test edge cases for US-only filtering"""
        extractor = ParallelMarcExtractor("dummy.xml", us_only=True)
        
        # Test with publication that has all the other attributes but wrong country
        edge_case_pub = Publication(
            title="Edge Case Book",
            author="Edge Author",
            pub_date="1950",
            source_id="edge_001",
            country_classification=CountryClassification.NON_US,
            author_type=AuthorType.CORPORATE,
        )
        edge_case_pub.year = 1950
        
        assert extractor._should_include_record(edge_case_pub) is False