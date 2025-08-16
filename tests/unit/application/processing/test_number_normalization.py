# tests/unit/application/processing/test_number_normalization.py

"""Test number normalization functionality restored from git history"""

# Third party imports
from pytest import fixture

# Local imports
from marc_pd_tool.application.processing.number_normalizer import NumberNormalizer
from marc_pd_tool.application.processing.similarity_calculator import (
    SimilarityCalculator,
)


class TestNumberNormalizer:
    """Test the restored NumberNormalizer class"""

    @fixture
    def normalizer(self):
        """Create a number normalizer instance"""
        return NumberNormalizer()

    def test_roman_numeral_normalization(self, normalizer):
        """Test Roman numeral to Arabic conversion"""
        # Test basic Roman numerals
        assert normalizer.normalize_numbers("Volume XIV", "eng") == "Volume 14"
        assert normalizer.normalize_numbers("Chapter III", "eng") == "Chapter 3"
        assert normalizer.normalize_numbers("Part VII", "eng") == "Part 7"

        # Test case insensitivity
        assert normalizer.normalize_numbers("volume xiv", "eng") == "volume 14"
        assert normalizer.normalize_numbers("VOLUME XIV", "eng") == "VOLUME 14"

    def test_ordinal_normalization(self, normalizer):
        """Test ordinal number normalization"""
        # English ordinals
        assert normalizer.normalize_numbers("1st edition", "eng") == "1 edition"
        assert normalizer.normalize_numbers("2nd volume", "eng") == "2 volume"
        assert normalizer.normalize_numbers("3rd chapter", "eng") == "3 chapter"
        assert normalizer.normalize_numbers("4th part", "eng") == "4 part"

        # Word ordinals
        assert normalizer.normalize_numbers("first edition", "eng") == "1 edition"
        assert normalizer.normalize_numbers("second volume", "eng") == "2 volume"
        assert normalizer.normalize_numbers("third chapter", "eng") == "3 chapter"

    def test_word_number_normalization(self, normalizer):
        """Test word number to digit conversion"""
        # Basic word numbers
        # Word numbers are converted individually, not as compound numbers
        assert normalizer.normalize_numbers("twenty one", "eng") == "20 1"
        assert normalizer.normalize_numbers("thirty three", "eng") == "30 3"
        # "hundred" is a special case that's mapped to "100"
        assert normalizer.normalize_numbers("one hundred", "eng") == "1 100"

    def test_combined_normalization(self, normalizer):
        """Test normalization with multiple number types"""
        text = "Volume XIV, 1st edition, twenty-one chapters"
        # Note: The config may not have all mappings, so we test what's there
        result = normalizer.normalize_numbers(text, "eng")
        assert "14" in result  # Roman numeral converted
        assert "1 " in result  # Ordinal converted


class TestSimilarityWithNumbers:
    """Test similarity calculation with number normalization"""

    @fixture
    def calculator(self):
        """Create a similarity calculator with number normalization"""
        return SimilarityCalculator()

    def test_title_similarity_with_roman_numerals(self, calculator):
        """Test that Roman numerals are normalized in title matching"""
        # These should match well after Roman numeral normalization
        score1 = calculator.calculate_title_similarity(
            "History Volume XIV", "History Volume 14", "eng"
        )
        # After normalization, these should be identical
        assert score1 > 90  # High similarity after normalization

    def test_title_similarity_with_ordinals(self, calculator):
        """Test that ordinals are normalized in title matching"""
        score = calculator.calculate_title_similarity(
            "1st Annual Report", "First Annual Report", "eng"
        )
        # These should match better after ordinal normalization
        assert score > 60  # Good similarity after normalization

    def test_author_similarity_with_numbers(self, calculator):
        """Test that numbers are normalized in author matching"""
        score = calculator.calculate_author_similarity("John Smith III", "John Smith 3", "eng")
        # Should have good similarity after Roman numeral normalization
        assert score > 80

    def test_publisher_similarity_with_numbers(self, calculator):
        """Test that numbers are normalized in publisher matching"""
        score = calculator.calculate_publisher_similarity(
            "XXI Century Publications", "21 Century Publications", "", "eng"  # No full text
        )
        # Should have good similarity after Roman numeral normalization
        assert score > 80
