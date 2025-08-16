# tests/unit/core/domain/test_publication.py

"""Tests for Publication class methods and utilities"""

# Standard library imports

# Third party imports

# Local imports
from marc_pd_tool.core.domain.enums import CountryClassification
from marc_pd_tool.core.domain.publication import Publication
from marc_pd_tool.shared.utils.text_utils import normalize_text_standard


class TestPublicationNormalization:
    """Test text normalization functionality"""

    def test_normalize_text_standard_basic(self):
        """Test basic text normalization"""
        assert normalize_text_standard("The Great Gatsby") == "the great gatsby"
        assert normalize_text_standard("TO KILL A MOCKINGBIRD") == "to kill a mockingbird"
        assert normalize_text_standard("1984") == "1984"

    def test_normalize_text_standard_punctuation_removal(self):
        """Test that punctuation is removed and replaced with spaces"""
        assert normalize_text_standard("The Great Gatsby: A Novel") == "the great gatsby a novel"
        assert normalize_text_standard("War & Peace") == "war peace"
        assert normalize_text_standard("Smith, John") == "smith john"
        # Word splitting normalization now joins single letters
        assert normalize_text_standard("U.S.A.") == "usa"
        assert normalize_text_standard("A.B.C.") == "abc"
        assert normalize_text_standard("Catcher in the Rye (1951)") == "catcher in the rye 1951"

    def test_normalize_text_standard_whitespace_handling(self):
        """Test that multiple whitespace is collapsed"""
        assert normalize_text_standard("The   Great    Gatsby") == "the great gatsby"
        assert normalize_text_standard("  Leading spaces") == "leading spaces"
        assert normalize_text_standard("Trailing spaces  ") == "trailing spaces"
        assert normalize_text_standard("\tTabs\tand\tnewlines\n") == "tabs and newlines"

    def test_normalize_text_standard_empty_and_none(self):
        """Test edge cases with empty or None text"""
        assert normalize_text_standard("") == ""
        assert normalize_text_standard("   ") == ""
        assert normalize_text_standard(None) == ""

    def test_normalize_text_standard_special_characters(self):
        """Test handling of various special characters"""
        assert normalize_text_standard("Naïve") == "naive"  # Accented chars folded to ASCII
        assert normalize_text_standard("Smith & Co.") == "smith co"
        assert normalize_text_standard("$100,000") == "100 000"
        assert normalize_text_standard("20th-century") == "20th century"


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

        # Properties now only do minimal cleanup (whitespace normalization)
        # Full normalization happens in SimilarityCalculator
        assert pub.title == "The Great Gatsby"  # Minimal cleanup only
        assert pub.author == "Fitzgerald, F. Scott"  # Minimal cleanup only
        assert pub.pub_date == "1925"  # Original preserved
        assert pub.publisher == "Scribner"  # Minimal cleanup only
        assert pub.place == "New York"  # Minimal cleanup only
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

        assert pub.title == "Test Book"  # Minimal cleanup only
        assert pub.author == "Test Author"  # Minimal cleanup only
        assert pub.edition == "First Edition"  # Minimal cleanup only
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

        assert pub.title == "Minimal Title"  # Minimal cleanup only
        assert pub.author == ""
        assert pub.pub_date is None
        assert pub.publisher == ""
        assert pub.place == ""
        assert pub.edition == ""
        assert pub.language_code == "eng"  # Now falls back to English
        assert pub.language_detection_status == "fallback_english"
        assert pub.source is None
        assert pub.source_id is None
        assert pub.country_code is None
        assert pub.full_text is None
        assert pub.year is None

    def test_publication_language_code_normalization(self):
        """Test that language codes are mapped to processing languages"""
        pub = Publication("Title", language_code="ENG")
        assert pub.language_code == "eng"
        assert pub.language_detection_status == "detected"

        pub = Publication("Title", language_code="FR")
        assert pub.language_code == "fre"  # Maps to processing language
        assert pub.language_detection_status == "detected"

        pub = Publication("Title", language_code="")
        assert pub.language_code == "eng"  # Falls back to English
        assert pub.language_detection_status == "fallback_english"

        # Test unknown language code fallback
        pub = Publication("Title", language_code="xyz")
        assert pub.language_code == "eng"  # Falls back to English
        assert pub.language_detection_status == "unknown_code"


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
            "lccn",
            "normalized_lccn",
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
        from marc_pd_tool.core.domain.match_result import MatchResult

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
        pub.registration_match = reg_match

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

    def test_registration_match_setter(self):
        """Test setting registration match"""
        # Local imports
        from marc_pd_tool.core.domain.match_result import MatchResult

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

        pub.registration_match = match

        assert pub.has_registration_match() is True
        assert pub.registration_match == match
        assert pub.registration_match.source_type == "registration"

    def test_renewal_match_setter(self):
        """Test setting renewal match"""
        # Local imports
        from marc_pd_tool.core.domain.match_result import MatchResult

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

        pub.renewal_match = match

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


class TestPublicationSortScore:
    """Test sort score calculation for quality-based ordering"""

    def test_sort_score_lccn_match_registration(self):
        """Test LCCN match gets highest score (1000)"""
        # Local imports
        from marc_pd_tool.core.domain.enums import MatchType
        from marc_pd_tool.core.domain.match_result import MatchResult

        pub = Publication("Test Book")
        match = MatchResult(
            matched_title="Test",
            matched_author="Author",
            similarity_score=50.0,  # Low similarity but LCCN match
            title_score=50.0,
            author_score=50.0,
            year_difference=0,
            source_id="reg_001",
            source_type="registration",
            match_type=MatchType.LCCN,
        )
        pub.registration_match = match

        score = pub.calculate_sort_score()
        assert score == 1000.0
        assert pub.sort_score == 1000.0

    def test_sort_score_lccn_match_renewal(self):
        """Test LCCN match in renewal gets highest score"""
        # Local imports
        from marc_pd_tool.core.domain.enums import MatchType
        from marc_pd_tool.core.domain.match_result import MatchResult

        pub = Publication("Test Book")
        match = MatchResult(
            matched_title="Test",
            matched_author="Author",
            similarity_score=50.0,
            title_score=50.0,
            author_score=50.0,
            year_difference=0,
            source_id="ren_001",
            source_type="renewal",
            match_type=MatchType.LCCN,
        )
        pub.renewal_match = match

        score = pub.calculate_sort_score()
        assert score == 1000.0

    def test_sort_score_both_matches(self):
        """Test both registration and renewal matches averages scores"""
        # Local imports
        from marc_pd_tool.core.domain.match_result import MatchResult

        pub = Publication("Test Book")

        reg_match = MatchResult(
            matched_title="Test",
            matched_author="Author",
            similarity_score=90.0,
            title_score=95.0,
            author_score=85.0,
            year_difference=0,
            source_id="reg_001",
            source_type="registration",
        )
        pub.registration_match = reg_match

        ren_match = MatchResult(
            matched_title="Test",
            matched_author="Author",
            similarity_score=80.0,
            title_score=85.0,
            author_score=75.0,
            year_difference=0,
            source_id="ren_001",
            source_type="renewal",
        )
        pub.renewal_match = ren_match

        score = pub.calculate_sort_score()
        assert score == 85.0  # (90 + 80) / 2

    def test_sort_score_registration_only(self):
        """Test registration-only match uses registration score"""
        # Local imports
        from marc_pd_tool.core.domain.match_result import MatchResult

        pub = Publication("Test Book")
        match = MatchResult(
            matched_title="Test",
            matched_author="Author",
            similarity_score=95.0,
            title_score=98.0,
            author_score=92.0,
            year_difference=0,
            source_id="reg_001",
            source_type="registration",
        )
        pub.registration_match = match

        score = pub.calculate_sort_score()
        assert score == 95.0

    def test_sort_score_renewal_only(self):
        """Test renewal-only match uses 90% of renewal score"""
        # Local imports
        from marc_pd_tool.core.domain.match_result import MatchResult

        pub = Publication("Test Book")
        match = MatchResult(
            matched_title="Test",
            matched_author="Author",
            similarity_score=80.0,
            title_score=85.0,
            author_score=75.0,
            year_difference=0,
            source_id="ren_001",
            source_type="renewal",
        )
        pub.renewal_match = match

        score = pub.calculate_sort_score()
        assert score == 72.0  # 80 * 0.9

    def test_sort_score_no_matches(self):
        """Test no matches results in score of 0"""
        pub = Publication("Test Book")
        score = pub.calculate_sort_score()
        assert score == 0.0


class TestPublicationDataCompleteness:
    """Test data completeness checking"""

    def test_data_completeness_all_complete(self):
        """Test when all data is complete"""
        pub = Publication(
            title="Test Book",
            author="Test Author",
            pub_date="1950",
            publisher="Test Publisher",
            place="New York",
            country_code="xxu",
            country_classification=CountryClassification.US,
        )
        pub.original_author = "Test Author"
        pub.original_publisher = "Test Publisher"

        issues = pub.check_data_completeness()
        assert issues == []
        assert pub.data_completeness == []

    def test_data_completeness_missing_year(self):
        """Test detection of missing year"""
        pub = Publication(title="Test Book", author="Test Author", publisher="Test Publisher")
        pub.original_author = "Test Author"
        pub.original_publisher = "Test Publisher"

        issues = pub.check_data_completeness()
        assert "missing_year" in issues

    def test_data_completeness_missing_publisher(self):
        """Test detection of missing publisher"""
        pub = Publication(title="Test Book", author="Test Author", pub_date="1950")
        pub.original_author = "Test Author"

        issues = pub.check_data_completeness()
        assert "missing_publisher" in issues

    def test_data_completeness_missing_author(self):
        """Test detection of missing author"""
        pub = Publication(title="Test Book", pub_date="1950", publisher="Test Publisher")
        pub.original_publisher = "Test Publisher"

        issues = pub.check_data_completeness()
        assert "missing_author" in issues

    def test_data_completeness_generic_title(self):
        """Test detection of generic title"""
        pub = Publication(
            title="Test Book", author="Test Author", pub_date="1950", publisher="Test Publisher"
        )
        pub.original_author = "Test Author"
        pub.original_publisher = "Test Publisher"
        pub.generic_title_detected = True

        issues = pub.check_data_completeness()
        assert "generic_title" in issues

    def test_data_completeness_unknown_country(self):
        """Test detection of unknown country"""
        pub = Publication(
            title="Test Book",
            author="Test Author",
            pub_date="1950",
            publisher="Test Publisher",
            country_classification=CountryClassification.UNKNOWN,
        )
        pub.original_author = "Test Author"
        pub.original_publisher = "Test Publisher"

        issues = pub.check_data_completeness()
        assert "unknown_country" in issues

    def test_data_completeness_multiple_issues(self):
        """Test detection of multiple issues"""
        pub = Publication(title="Test Book")
        pub.generic_title_detected = True

        issues = pub.check_data_completeness()
        assert "missing_year" in issues
        assert "missing_publisher" in issues
        assert "missing_author" in issues
        assert "generic_title" in issues
        assert len(issues) >= 4


class TestPublicationPickling:
    """Test pickle serialization/deserialization"""

    def test_pickle_basic_publication(self):
        """Test pickling a basic publication"""
        # Standard library imports
        import pickle

        pub = Publication(
            title="Test Book", author="Test Author", pub_date="1950", publisher="Test Publisher"
        )
        pub.copyright_status = "US_NO_MATCH"

        # Pickle and unpickle
        pickled = pickle.dumps(pub)
        restored = pickle.loads(pickled)

        assert restored.title == pub.title
        assert restored.author == pub.author
        assert restored.year == pub.year
        assert restored.publisher == pub.publisher
        assert restored.copyright_status == pub.copyright_status

    def test_pickle_publication_with_matches(self):
        """Test pickling publication with match results"""
        # Standard library imports
        import pickle

        # Local imports
        from marc_pd_tool.core.domain.match_result import MatchResult

        pub = Publication("Test Book", author="Test Author", pub_date="1950")

        # Add a match
        match = MatchResult(
            matched_title="Test",
            matched_author="Author",
            similarity_score=90.0,
            title_score=95.0,
            author_score=85.0,
            year_difference=0,
            source_id="reg_001",
            source_type="registration",
        )
        pub.registration_match = match

        # Pickle and unpickle
        pickled = pickle.dumps(pub)
        restored = pickle.loads(pickled)

        assert restored.registration_match is not None
        assert restored.registration_match.similarity_score == 90.0
        assert restored.registration_match.source_id == "reg_001"

    def test_pickle_clears_cached_properties(self):
        """Test that cached properties are cleared after unpickling"""
        # Standard library imports
        import pickle

        pub = Publication(title="Test Book", author="Test Author")

        # Access properties to populate cache
        _ = pub.title
        _ = pub.author

        # Pickle and unpickle
        pickled = pickle.dumps(pub)
        restored = pickle.loads(pickled)

        # Cached properties should be None after unpickling
        assert restored._cached_title is None
        assert restored._cached_author is None

        # But properties should still work
        assert restored.title == "Test Book"
        assert restored.author == "Test Author"
