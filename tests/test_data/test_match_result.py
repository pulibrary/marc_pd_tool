"""Tests for MatchResult dataclass"""

# Third party imports
from pytest import raises

# Local imports
from marc_pd_tool.data.publication import MatchResult


class TestMatchResultCreation:
    """Test MatchResult dataclass creation and field assignment"""

    def test_match_result_required_fields(self):
        """Test MatchResult creation with all required fields"""
        match = MatchResult(
            matched_title="Test Book",
            matched_author="Test Author",
            similarity_score=85.5,
            title_score=90.0,
            author_score=75.0,
            year_difference=1,
            source_id="reg_001",
            source_type="registration",
        )

        assert match.matched_title == "Test Book"
        assert match.matched_author == "Test Author"
        assert match.similarity_score == 85.5
        assert match.title_score == 90.0
        assert match.author_score == 75.0
        assert match.year_difference == 1
        assert match.source_id == "reg_001"
        assert match.source_type == "registration"

    def test_match_result_with_optional_fields(self):
        """Test MatchResult creation with optional fields"""
        match = MatchResult(
            matched_title="Test Book",
            matched_author="Test Author",
            similarity_score=85.5,
            title_score=90.0,
            author_score=75.0,
            year_difference=1,
            source_id="reg_001",
            source_type="registration",
            matched_date="1950-01-01",
            matched_publisher="Test Publisher",
            publisher_score=80.0,
        )

        assert match.matched_date == "1950-01-01"
        assert match.matched_publisher == "Test Publisher"
        assert match.publisher_score == 80.0

    def test_match_result_default_optional_fields(self):
        """Test that optional fields have correct defaults"""
        match = MatchResult(
            matched_title="Test Book",
            matched_author="Test Author",
            similarity_score=85.5,
            title_score=90.0,
            author_score=75.0,
            year_difference=1,
            source_id="reg_001",
            source_type="registration",
        )

        assert match.matched_date == ""
        assert match.matched_publisher == ""
        assert match.publisher_score == 0.0


class TestMatchResultDataTypes:
    """Test MatchResult field data types and validation"""

    def test_match_result_string_fields(self):
        """Test string field handling"""
        match = MatchResult(
            matched_title="",  # Empty string
            matched_author="Author with special chars: àéíóú",
            similarity_score=85.5,
            title_score=90.0,
            author_score=75.0,
            year_difference=1,
            source_id="uuid-123-456",
            source_type="renewal",
            matched_date="1950-12-31",
            matched_publisher="Publisher & Co.",
        )

        assert match.matched_title == ""
        assert "àéíóú" in match.matched_author
        assert match.source_id == "uuid-123-456"
        assert match.source_type == "renewal"
        assert match.matched_date == "1950-12-31"
        assert match.matched_publisher == "Publisher & Co."

    def test_match_result_numeric_fields(self):
        """Test numeric field handling"""
        match = MatchResult(
            matched_title="Test",
            matched_author="Test Author",
            similarity_score=100.0,  # Max score
            title_score=0.0,  # Min score
            author_score=50.5,  # Decimal score
            year_difference=0,  # No difference
            source_id="test_001",
            source_type="registration",
            publisher_score=99.99,  # High precision
        )

        assert match.similarity_score == 100.0
        assert match.title_score == 0.0
        assert match.author_score == 50.5
        assert match.year_difference == 0
        assert match.publisher_score == 99.99

    def test_match_result_negative_year_difference(self):
        """Test handling of negative year differences"""
        match = MatchResult(
            matched_title="Test Book",
            matched_author="Test Author",
            similarity_score=85.5,
            title_score=90.0,
            author_score=75.0,
            year_difference=-2,  # Negative difference
            source_id="reg_001",
            source_type="registration",
        )

        assert match.year_difference == -2


class TestMatchResultEquality:
    """Test MatchResult equality and comparison"""

    def test_match_result_equality(self):
        """Test that identical MatchResults are equal"""
        match1 = MatchResult(
            matched_title="Test Book",
            matched_author="Test Author",
            similarity_score=85.5,
            title_score=90.0,
            author_score=75.0,
            year_difference=1,
            source_id="reg_001",
            source_type="registration",
        )

        match2 = MatchResult(
            matched_title="Test Book",
            matched_author="Test Author",
            similarity_score=85.5,
            title_score=90.0,
            author_score=75.0,
            year_difference=1,
            source_id="reg_001",
            source_type="registration",
        )

        assert match1 == match2

    def test_match_result_inequality(self):
        """Test that different MatchResults are not equal"""
        match1 = MatchResult(
            matched_title="Test Book",
            matched_author="Test Author",
            similarity_score=85.5,
            title_score=90.0,
            author_score=75.0,
            year_difference=1,
            source_id="reg_001",
            source_type="registration",
        )

        match2 = MatchResult(
            matched_title="Different Book",  # Different title
            matched_author="Test Author",
            similarity_score=85.5,
            title_score=90.0,
            author_score=75.0,
            year_difference=1,
            source_id="reg_001",
            source_type="registration",
        )

        assert match1 != match2

    def test_match_result_inequality_scores(self):
        """Test inequality based on different scores"""
        match1 = MatchResult(
            matched_title="Test Book",
            matched_author="Test Author",
            similarity_score=85.5,
            title_score=90.0,
            author_score=75.0,
            year_difference=1,
            source_id="reg_001",
            source_type="registration",
        )

        match2 = MatchResult(
            matched_title="Test Book",
            matched_author="Test Author",
            similarity_score=88.0,  # Different score
            title_score=90.0,
            author_score=75.0,
            year_difference=1,
            source_id="reg_001",
            source_type="registration",
        )

        assert match1 != match2


class TestMatchResultEdgeCases:
    """Test edge cases and special scenarios"""

    def test_match_result_with_empty_strings(self):
        """Test MatchResult with empty string values"""
        match = MatchResult(
            matched_title="",
            matched_author="",
            similarity_score=0.0,
            title_score=0.0,
            author_score=0.0,
            year_difference=0,
            source_id="",
            source_type="",
            matched_date="",
            matched_publisher="",
        )

        assert match.matched_title == ""
        assert match.matched_author == ""
        assert match.source_id == ""
        assert match.source_type == ""
        assert match.matched_date == ""
        assert match.matched_publisher == ""

    def test_match_result_with_unicode_characters(self):
        """Test MatchResult with Unicode characters"""
        match = MatchResult(
            matched_title="Tëst Bøøk with ümlauts",
            matched_author="Authör with àccénts",
            similarity_score=85.5,
            title_score=90.0,
            author_score=75.0,
            year_difference=1,
            source_id="unicode_test_001",
            source_type="registration",
            matched_publisher="Publîsher & Çø.",
        )

        assert "ø" in match.matched_title
        assert "ö" in match.matched_author
        assert "î" in match.matched_publisher

    def test_match_result_source_type_variations(self):
        """Test different source type values"""
        # Registration match
        reg_match = MatchResult(
            matched_title="Test Book",
            matched_author="Test Author",
            similarity_score=85.5,
            title_score=90.0,
            author_score=75.0,
            year_difference=1,
            source_id="reg_001",
            source_type="registration",
        )
        assert reg_match.source_type == "registration"

        # Renewal match
        ren_match = MatchResult(
            matched_title="Test Book",
            matched_author="Test Author",
            similarity_score=85.5,
            title_score=90.0,
            author_score=75.0,
            year_difference=1,
            source_id="ren_001",
            source_type="renewal",
        )
        assert ren_match.source_type == "renewal"

    def test_match_result_extreme_scores(self):
        """Test MatchResult with extreme score values"""
        match = MatchResult(
            matched_title="Test Book",
            matched_author="Test Author",
            similarity_score=0.001,  # Very low score
            title_score=99.999,  # Very high score
            author_score=50.0,  # Exact middle
            year_difference=100,  # Large year difference
            source_id="extreme_test",
            source_type="registration",
            publisher_score=0.0,  # Zero publisher score
        )

        assert match.similarity_score == 0.001
        assert match.title_score == 99.999
        assert match.author_score == 50.0
        assert match.year_difference == 100
        assert match.publisher_score == 0.0

    def test_match_result_large_year_differences(self):
        """Test MatchResult with large year differences"""
        match = MatchResult(
            matched_title="Ancient Book",
            matched_author="Ancient Author",
            similarity_score=85.5,
            title_score=90.0,
            author_score=75.0,
            year_difference=50,  # Large positive difference
            source_id="ancient_001",
            source_type="registration",
        )

        assert match.year_difference == 50

        # Test large negative difference
        match_neg = MatchResult(
            matched_title="Future Book",
            matched_author="Future Author",
            similarity_score=85.5,
            title_score=90.0,
            author_score=75.0,
            year_difference=-25,  # Large negative difference
            source_id="future_001",
            source_type="registration",
        )

        assert match_neg.year_difference == -25


class TestMatchResultRepr:
    """Test MatchResult string representation"""

    def test_match_result_repr(self):
        """Test that MatchResult has a useful string representation"""
        match = MatchResult(
            matched_title="Test Book",
            matched_author="Test Author",
            similarity_score=85.5,
            title_score=90.0,
            author_score=75.0,
            year_difference=1,
            source_id="reg_001",
            source_type="registration",
        )

        repr_str = repr(match)

        # Check that key fields are in the representation
        assert "Test Book" in repr_str
        assert "Test Author" in repr_str
        assert "85.5" in repr_str
        assert "reg_001" in repr_str
        assert "registration" in repr_str
