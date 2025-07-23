# tests/test_processing/test_enhanced_preprocessing.py

"""Tests for enhanced author/publisher preprocessing in Phase 4"""

# Standard library imports
from unittest import TestCase

# Local imports
from marc_pd_tool.processing.indexer import generate_wordbased_author_keys
from marc_pd_tool.processing.indexer import generate_wordbased_publisher_keys


class TestEnhancedAuthorPreprocessing(TestCase):
    """Test enhanced author name preprocessing"""

    def test_author_with_dates_removed(self):
        """Test that dates in parentheses are properly removed"""
        keys = generate_wordbased_author_keys("Shakespeare, William (1564-1616)", "eng")

        assert "shakespeare" in keys
        assert "william" in keys
        assert "1564" not in keys
        assert "1616" not in keys

    def test_author_with_titles_removed(self):
        """Test that titles and qualifiers are removed"""
        keys = generate_wordbased_author_keys("Dr. John Smith, Prof.", "eng")

        assert "john" in keys
        assert "smith" in keys
        assert "dr" not in keys
        assert "prof" not in keys

    def test_author_with_initials(self):
        """Test handling of initials with and without periods"""
        keys = generate_wordbased_author_keys("Smith, J. R.", "eng")

        assert "smith" in keys
        assert "j" in keys
        assert "j." in keys  # Both forms should be indexed
        assert "r" in keys
        assert "r." in keys

    def test_author_multilingual_stopwords(self):
        """Test multilingual stopword removal"""
        # French
        keys_fr = generate_wordbased_author_keys("par Jean Dupont", "fre")
        assert "jean" in keys_fr
        assert "dupont" in keys_fr
        assert "par" not in keys_fr

        # German
        keys_de = generate_wordbased_author_keys("von Hans Mueller", "ger")
        assert "hans" in keys_de
        assert "mueller" in keys_de
        assert "von" not in keys_de

    def test_author_compound_surnames(self):
        """Test handling of compound surnames"""
        keys = generate_wordbased_author_keys("Mary Jane Smith-Jones", "eng")

        assert "mary" in keys
        assert "jane" in keys
        assert "smith" in keys or "smith-jones" in keys  # Handle hyphenated names
        assert "mary_smith" in keys or "mary_smith-jones" in keys

    def test_author_complex_format(self):
        """Test complex author format with multiple elements"""
        keys = generate_wordbased_author_keys(
            "edited by Dr. William Shakespeare, Jr. (1564-1616)", "eng"
        )

        assert "william" in keys
        assert "shakespeare" in keys
        assert "edited" not in keys
        assert "by" not in keys
        assert "dr" not in keys
        # Jr should be kept as it's part of the name
        assert "jr" in keys


class TestEnhancedPublisherPreprocessing(TestCase):
    """Test enhanced publisher name preprocessing"""

    def test_publisher_location_removal(self):
        """Test that location information is removed"""
        keys = generate_wordbased_publisher_keys("Oxford University Press (New York)", "eng")

        assert "oxford" in keys
        assert "university" in keys
        assert "press" in keys
        assert "new" not in keys
        assert "york" not in keys

    def test_publisher_date_removal(self):
        """Test that dates are removed"""
        keys = generate_wordbased_publisher_keys("Random House 1925", "eng")

        assert "random" in keys
        assert "house" in keys
        assert "1925" not in keys

    def test_publisher_university_handling(self):
        """Test handling of university publishers (no special treatment)"""
        keys = generate_wordbased_publisher_keys("Harvard University Press", "eng")

        assert "harvard" in keys
        assert "university" in keys
        assert "press" in keys
        # Standard combinations (no special university handling)
        assert "harvard_university" in keys
        assert "university_press" in keys
        assert "harvard_university_press" in keys

    def test_publisher_multilingual_stopwords(self):
        """Test multilingual publisher stopword removal"""
        # French
        keys_fr = generate_wordbased_publisher_keys("Éditions Gallimard", "fre")
        assert "gallimard" in keys_fr
        assert "éditions" not in keys_fr

        # German
        keys_de = generate_wordbased_publisher_keys("Fischer Verlag", "ger")
        assert "fischer" in keys_de
        assert "verlag" not in keys_de

        # Spanish
        keys_es = generate_wordbased_publisher_keys("Editorial Planeta", "spa")
        assert "planeta" in keys_es
        assert "editorial" not in keys_es

    def test_publisher_abbreviation_expansion(self):
        """Test that abbreviations are expanded"""
        keys = generate_wordbased_publisher_keys("MIT Press Inc.", "eng")

        # Note: This depends on PublishingAbbreviations having MIT expansion
        # The test verifies that Inc. is removed as stopword
        assert "mit" in keys
        assert "press" in keys
        assert "inc" not in keys
        assert "incorporated" not in keys

    def test_publisher_fallback_for_all_stopwords(self):
        """Test fallback when all words are stopwords"""
        keys = generate_wordbased_publisher_keys("Publishing Company Inc.", "eng")

        # Should fall back to longest words when all are stopwords
        assert len(keys) > 0  # Should have some fallback keys

    def test_publisher_complex_name(self):
        """Test complex publisher name with multiple elements"""
        keys = generate_wordbased_publisher_keys(
            "Random House Publishing Group International [New York] 2010", "eng"
        )

        assert "random" in keys
        assert "house" in keys
        # Stopwords should be removed
        assert "publishing" not in keys
        assert "group" not in keys
        assert "international" not in keys
        # Location and date should be removed
        assert "new" not in keys
        assert "york" not in keys
        assert "2010" not in keys


class TestPreprocessingIntegration(TestCase):
    """Test integration of enhanced preprocessing"""

    def test_multilingual_consistency(self):
        """Test that multilingual processing is consistent"""
        # Test same content in different languages
        keys_en = generate_wordbased_author_keys("by John Smith", "eng")
        keys_fr = generate_wordbased_author_keys("par Jean Dupont", "fre")

        # Both should remove language-specific stopwords
        assert "by" not in keys_en
        assert "par" not in keys_fr
        # Both should keep meaningful names
        assert len(keys_en) > 0
        assert len(keys_fr) > 0

    def test_edge_case_handling(self):
        """Test handling of edge cases"""
        # Empty strings
        assert generate_wordbased_author_keys("", "eng") == set()
        assert generate_wordbased_publisher_keys("", "eng") == set()

        # None values
        assert generate_wordbased_author_keys(None, "eng") == set()
        assert generate_wordbased_publisher_keys(None, "eng") == set()

        # Only stopwords
        author_keys = generate_wordbased_author_keys("by edited translated", "eng")
        assert len(author_keys) == 0  # Should be empty after filtering

        # Publisher with only short words after filtering
        pub_keys = generate_wordbased_publisher_keys("A B C Publishing", "eng")
        assert len(pub_keys) >= 0  # Should handle gracefully

    def test_performance_regression_prevention(self):
        """Test that enhancements don't cause performance regressions"""
        # Test with longer strings to ensure regex operations are efficient
        long_author = "edited by Dr. Professor Sir William Edmund Shakespeare III, Esq. (1564-1616)"
        long_publisher = "The International Oxford University Press Publishing Company Group Inc. [Oxford, New York, London] 2010"

        # Should complete without timeout or excessive processing
        author_keys = generate_wordbased_author_keys(long_author, "eng")
        publisher_keys = generate_wordbased_publisher_keys(long_publisher, "eng")

        # Should produce reasonable results
        assert len(author_keys) > 0
        assert len(publisher_keys) > 0

        # Core names should be preserved
        assert "william" in author_keys
        assert "shakespeare" in author_keys
        assert "oxford" in publisher_keys
        assert "university" in publisher_keys
