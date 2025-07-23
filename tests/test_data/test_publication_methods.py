"""Tests for Publication class methods and utilities"""

# Standard library imports
from typing import Optional

# Third party imports
from pytest import fixture

# Local imports
from marc_pd_tool.data.enums import CountryClassification
from marc_pd_tool.data.publication import Publication


class TestPublicationNormalization:
    """Test text normalization functionality"""

    def test_normalize_text_basic(self):
        """Test basic text normalization"""
        assert Publication.normalize_text("The Great Gatsby") == "the great gatsby"
        assert Publication.normalize_text("TO KILL A MOCKINGBIRD") == "to kill a mockingbird"
        assert Publication.normalize_text("1984") == "1984"

    def test_normalize_text_punctuation_removal(self):
        """Test that punctuation is removed and replaced with spaces"""
        assert Publication.normalize_text("The Great Gatsby: A Novel") == "the great gatsby a novel"
        assert Publication.normalize_text("War & Peace") == "war peace"
        assert Publication.normalize_text("Smith, John") == "smith john"
        assert Publication.normalize_text("U.S.A.") == "u s a"
        assert Publication.normalize_text("Catcher in the Rye (1951)") == "catcher in the rye 1951"

    def test_normalize_text_whitespace_handling(self):
        """Test that multiple whitespace is collapsed"""
        assert Publication.normalize_text("The   Great    Gatsby") == "the great gatsby"
        assert Publication.normalize_text("  Leading spaces") == "leading spaces"
        assert Publication.normalize_text("Trailing spaces  ") == "trailing spaces"
        assert Publication.normalize_text("\tTabs\tand\tnewlines\n") == "tabs and newlines"

    def test_normalize_text_empty_and_none(self):
        """Test edge cases with empty or None text"""
        assert Publication.normalize_text("") == ""
        assert Publication.normalize_text("   ") == ""
        assert Publication.normalize_text(None) == ""

    def test_normalize_text_special_characters(self):
        """Test handling of various special characters"""
        assert Publication.normalize_text("Naïve") == "naïve"  # Accented chars preserved
        assert Publication.normalize_text("Smith & Co.") == "smith co"
        assert Publication.normalize_text("$100,000") == "100 000"
        assert Publication.normalize_text("20th-century") == "20th century"


class TestPublicationYearExtraction:
    """Test year extraction from publication dates"""

    def test_extract_year_four_digit_years(self):
        """Test extraction of standard 4-digit years"""
        pub = Publication("Title", pub_date="1984")
        assert pub.year == 1984

        pub = Publication("Title", pub_date="2023")
        assert pub.year == 2023

        pub = Publication("Title", pub_date="1901")
        assert pub.year == 1901

    def test_extract_year_from_full_dates(self):
        """Test extraction from full date strings"""
        pub = Publication("Title", pub_date="1984-05-15")
        assert pub.year == 1984

        pub = Publication("Title", pub_date="May 15, 1984")
        assert pub.year == 1984

        pub = Publication("Title", pub_date="Published in 1984")
        assert pub.year == 1984

    def test_extract_year_multiple_years(self):
        """Test that first valid year is extracted when multiple present"""
        pub = Publication("Title", pub_date="Reprinted 1984 from 1922 original")
        assert pub.year == 1984  # First valid year found

        pub = Publication("Title", pub_date="1922-1984")
        assert pub.year == 1922

    def test_extract_year_invalid_dates(self):
        """Test handling of invalid or missing dates"""
        pub = Publication("Title", pub_date="")
        assert pub.year is None

        pub = Publication("Title", pub_date="No date")
        assert pub.year is None

        pub = Publication("Title", pub_date="18th century")
        assert pub.year is None

        pub = Publication("Title", pub_date="Ancient")
        assert pub.year is None

    def test_extract_year_edge_cases(self):
        """Test edge cases for year extraction"""
        # Years from 1800s should now be accepted (expanded regex)
        pub = Publication("Title", pub_date="1899")
        assert pub.year == 1899

        # Years in the future (beyond 2099) should be rejected
        pub = Publication("Title", pub_date="2100")
        assert pub.year is None

        # Three-digit years should be rejected
        pub = Publication("Title", pub_date="984")
        assert pub.year is None


class TestPublicationConstruction:
    """Test Publication object construction and field assignment"""

    def test_publication_basic_construction(self):
        """Test basic publication construction with required fields"""
        pub = Publication(
            title="The Great Gatsby",
            author="Fitzgerald, F. Scott",
            pub_date="1925",
            publisher="Scribner",
            place="New York",
        )

        assert pub.title == "the great gatsby"  # Normalized
        assert pub.author == "fitzgerald f scott"  # Normalized
        assert pub.pub_date == "1925"  # Original preserved
        assert pub.publisher == "scribner"  # Normalized
        assert pub.place == "new york"  # Normalized
        assert pub.year == 1925  # Extracted
        assert pub.country_classification == CountryClassification.UNKNOWN  # Default

    def test_publication_with_all_fields(self):
        """Test publication construction with all possible fields"""
        pub = Publication(
            title="Test Book",
            author="Test Author",
            pub_date="1950-01-01",
            publisher="Test Publisher",
            place="Test City",
            edition="First Edition",
            language_code="eng",
            source="MARC",
            source_id="test_001",
            country_code="xxu",
            country_classification=CountryClassification.US,
            full_text="Complete text of the work",
        )

        assert pub.title == "test book"
        assert pub.author == "test author"
        assert pub.edition == "first edition"
        assert pub.language_code == "eng"
        assert pub.source == "MARC"
        assert pub.source_id == "test_001"
        assert pub.country_code == "xxu"
        assert pub.country_classification == CountryClassification.US
        assert pub.full_text == "Complete text of the work"

        # Check original values are preserved
        assert pub.original_title == "Test Book"
        assert pub.original_author == "Test Author"
        assert pub.original_publisher == "Test Publisher"

    def test_publication_minimal_construction(self):
        """Test publication construction with only title"""
        pub = Publication("Minimal Title")

        assert pub.title == "minimal title"
        assert pub.author == ""
        assert pub.pub_date is None
        assert pub.publisher == ""
        assert pub.place == ""
        assert pub.edition == ""
        assert pub.language_code is None
        assert pub.source is None
        assert pub.source_id is None
        assert pub.country_code is None
        assert pub.full_text is None
        assert pub.year is None

    def test_publication_language_code_normalization(self):
        """Test that language codes are normalized to lowercase"""
        pub = Publication("Title", language_code="ENG")
        assert pub.language_code == "eng"

        pub = Publication("Title", language_code="FR")
        assert pub.language_code == "fr"

        pub = Publication("Title", language_code="")
        assert pub.language_code is None


class TestPublicationToDictMethod:
    """Test the to_dict method functionality"""

    def test_to_dict_basic(self):
        """Test basic to_dict functionality"""
        pub = Publication(
            title="Test Book",
            author="Test Author",
            pub_date="1950",
            publisher="Test Publisher",
            place="Test City",
            source_id="test_001",
        )

        result = pub.to_dict()

        # Check that all expected keys are present
        expected_keys = {
            "title",
            "author",
            "main_author",
            "pub_date",
            "publisher",
            "place",
            "edition",
            "language_code",
            "source",
            "source_id",
            "year",
            "country_code",
            "country_classification",
            "copyright_status",
            "full_text",
            "registration_match",
            "renewal_match",
        }
        assert set(result.keys()) == expected_keys

        # Check original values are preserved in dict
        assert result["title"] == "Test Book"  # Original, not normalized
        assert result["author"] == "Test Author"  # Original, not normalized
        assert result["publisher"] == "Test Publisher"  # Original, not normalized
        assert result["year"] == 1950

    def test_to_dict_with_matches(self):
        """Test to_dict with match results"""
        # Local imports
        from marc_pd_tool.data.publication import MatchResult

        pub = Publication("Test Book", author="Test Author", pub_date="1950")

        # Add a registration match
        reg_match = MatchResult(
            matched_title="Test Book (matched)",
            matched_author="Test Author (matched)",
            similarity_score=85.5,
            title_score=90.0,
            author_score=75.0,
            year_difference=1,
            source_id="reg_001",
            source_type="registration",
        )
        pub.set_registration_match(reg_match)

        result = pub.to_dict()

        # Check registration match is included
        assert result["registration_match"] is not None
        reg_data = result["registration_match"]
        assert reg_data["matched_title"] == "Test Book (matched)"
        assert reg_data["similarity_score"] == 85.5
        assert reg_data["title_score"] == 90.0
        assert reg_data["source_id"] == "reg_001"

        # Check renewal match is None
        assert result["renewal_match"] is None

    def test_to_dict_no_matches(self):
        """Test to_dict when no matches are present"""
        pub = Publication("Test Book")
        result = pub.to_dict()

        assert result["registration_match"] is None
        assert result["renewal_match"] is None


class TestPublicationMatchHandling:
    """Test match setting and retrieval functionality"""

    def test_set_registration_match(self):
        """Test setting registration match"""
        # Local imports
        from marc_pd_tool.data.publication import MatchResult

        pub = Publication("Test Book")
        match = MatchResult(
            matched_title="Test Book",
            matched_author="Test Author",
            similarity_score=90.0,
            title_score=95.0,
            author_score=85.0,
            year_difference=0,
            source_id="reg_001",
            source_type="registration",
        )

        pub.set_registration_match(match)

        assert pub.has_registration_match() is True
        assert pub.registration_match == match
        assert pub.registration_match.source_type == "registration"

    def test_set_renewal_match(self):
        """Test setting renewal match"""
        # Local imports
        from marc_pd_tool.data.publication import MatchResult

        pub = Publication("Test Book")
        match = MatchResult(
            matched_title="Test Book",
            matched_author="Test Author",
            similarity_score=88.0,
            title_score=92.0,
            author_score=80.0,
            year_difference=1,
            source_id="ren_001",
            source_type="renewal",
        )

        pub.set_renewal_match(match)

        assert pub.has_renewal_match() is True
        assert pub.renewal_match == match
        assert pub.renewal_match.source_type == "renewal"

    def test_no_matches_initially(self):
        """Test that publications start with no matches"""
        pub = Publication("Test Book")

        assert pub.has_registration_match() is False
        assert pub.has_renewal_match() is False
        assert pub.registration_match is None
        assert pub.renewal_match is None
