"""Tests for key generation in indexing system"""

# Third party imports
# pytest imported automatically by test runner

# Local imports
from marc_pd_tool.processing.indexer import generate_author_keys
from marc_pd_tool.processing.indexer import generate_title_keys
from marc_pd_tool.utils.text_utils import extract_significant_words
from marc_pd_tool.utils.text_utils import normalize_text

# Test stopwords matching original hardcoded behavior
TEST_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "has",
    "he",
    "in",
    "is",
    "it",
    "its",
    "of",
    "on",
    "or",
    "that",
    "the",
    "to",
    "was",
    "were",
    "will",
    "with",
}


class TestTextNormalization:
    """Test text normalization functions"""

    def test_normalize_text_basic(self):
        """Test basic text normalization"""
        assert normalize_text("The Great American Novel!") == "the great american novel"
        assert normalize_text("Smith, John A.") == "smith john a"
        assert normalize_text("Multiple   Spaces") == "multiple spaces"

    def test_normalize_text_punctuation(self):
        """Test punctuation removal"""
        assert normalize_text("Title: A Subtitle (Revised)") == "title a subtitle revised"
        assert normalize_text("Author, Jr.") == "author jr"
        assert normalize_text("Hyphen-ated") == "hyphen ated"

    def test_extract_significant_words(self):
        """Test significant word extraction"""
        words = extract_significant_words("The Great American Novel", TEST_STOPWORDS)
        assert "great" in words
        assert "american" in words
        assert "novel" in words
        assert "the" not in words  # Stopword filtered

    def test_extract_significant_words_edge_cases(self):
        """Test edge cases for word extraction"""
        # Empty string
        assert extract_significant_words("", TEST_STOPWORDS) == []

        # Only stopwords
        words = extract_significant_words("the a an of", TEST_STOPWORDS)
        assert len(words) <= 1  # Should keep at least one word if possible

        # Short words filtered
        words = extract_significant_words("a bb ccc dddd", TEST_STOPWORDS)
        assert "bb" not in words  # Too short
        assert "ccc" in words
        assert "dddd" in words


class TestTitleKeys:
    """Test title key generation"""

    def test_title_keys_basic(self):
        """Test basic title key generation"""
        keys = generate_title_keys("The Great American Novel", TEST_STOPWORDS)

        # Should contain individual words
        assert "great" in keys
        assert "american" in keys
        assert "novel" in keys

        # Should contain multi-word combinations
        assert "great_american" in keys
        assert "american_novel" in keys
        assert "great_american_novel" in keys

    def test_title_keys_no_stopwords(self):
        """Test that stopwords are filtered from keys"""
        keys = generate_title_keys("The Great American Novel", TEST_STOPWORDS)
        assert "the" not in keys

    def test_title_keys_short_titles(self):
        """Test key generation for short titles"""
        keys = generate_title_keys("Novel", TEST_STOPWORDS)
        assert "novel" in keys
        assert len(keys) >= 1

        keys = generate_title_keys("Great Novel", TEST_STOPWORDS)
        assert "great" in keys
        assert "novel" in keys
        assert "great_novel" in keys

    def test_title_keys_empty(self):
        """Test key generation for empty/invalid titles"""
        assert generate_title_keys("", TEST_STOPWORDS) == set()
        assert generate_title_keys("   ", TEST_STOPWORDS) == set()

        # Note: "the a an" will generate metaphone keys even if all words are stopwords
        keys = generate_title_keys("the a an", TEST_STOPWORDS)
        assert len(keys) <= 4  # Should be minimal, mostly metaphone keys if available


class TestAuthorKeys:
    """Test author key generation"""

    def test_author_keys_last_first_format(self):
        """Test author keys for 'Last, First' format (personal names)"""
        keys = generate_author_keys("Smith, John A.")

        # Should contain surname
        assert "smith" in keys

        # Should contain surname + first name combinations
        assert "smith_john" in keys or "smith_a" in keys

        # Should contain reversed format
        assert any("john" in key for key in keys)

    def test_author_keys_first_last_format(self):
        """Test author keys for 'First Last' format (personal names)"""
        keys = generate_author_keys("John Smith")

        assert "smith" in keys  # Surname
        assert "john_smith" in keys  # First + Last
        assert "smith_john" in keys  # Reversed

    def test_author_keys_single_name(self):
        """Test author keys for single names (personal names)"""
        keys = generate_author_keys("Shakespeare")
        assert "shakespeare" in keys

        keys = generate_author_keys("Voltaire")
        assert "voltaire" in keys

    def test_author_keys_complex_names(self):
        """Test author keys for complex name formats (personal names)"""
        # Multiple middle names
        keys = generate_author_keys("Smith, John William Alexander")
        assert "smith" in keys
        assert "smith_john" in keys

        # Jr./Sr. suffixes
        keys = generate_author_keys("King, Martin Luther Jr.")
        assert "king" in keys
        assert any("martin" in key for key in keys)

    def test_author_keys_empty(self):
        """Test author key generation for empty authors"""
        assert generate_author_keys("") == set()
        assert generate_author_keys("   ") == set()

    def test_author_keys_non_personal_names(self):
        """Test author keys for non-personal names (now treated as personal names)

        Since we simplified to use only personal name parsing for all authors from 245$c,
        these should still generate keys but using personal name logic.
        """
        # Corporate-style name - treated as personal name (uses last word as surname)
        keys = generate_author_keys("Harvard University Press")
        assert "press" in keys  # Last word treated as surname
        assert len(keys) > 0

        # Multi-part name with periods
        keys = generate_author_keys("United States Congress")
        assert "congress" in keys  # Last word
        assert "united_congress" in keys  # First + Last
        assert len(keys) > 0


class TestKeyGeneration:
    """Integration tests for key generation"""

    def test_key_generation_preserves_matching(self):
        """Test that similar titles/authors generate overlapping keys"""
        # Similar titles should share keys
        keys1 = generate_title_keys("The Great Gatsby", TEST_STOPWORDS)
        keys2 = generate_title_keys("Great Gatsby", TEST_STOPWORDS)
        keys3 = generate_title_keys("The Great Gatsby: A Novel", TEST_STOPWORDS)

        # Should have overlapping keys
        assert len(keys1 & keys2) > 0
        assert len(keys1 & keys3) > 0

        # Similar authors should share keys
        auth_keys1 = generate_author_keys("Fitzgerald, F. Scott")
        auth_keys2 = generate_author_keys("Fitzgerald, Francis Scott")
        auth_keys3 = generate_author_keys("F. Scott Fitzgerald")

        assert len(auth_keys1 & auth_keys2) > 0
        assert len(auth_keys1 & auth_keys3) > 0

    def test_key_generation_handles_variations(self):
        """Test that common bibliographic variations are handled"""
        # Title variations
        variations = [
            "Introduction to Physics",
            "Physics: An Introduction",
            "An Introduction to Physics",
        ]

        all_keys = [generate_title_keys(title, TEST_STOPWORDS) for title in variations]

        # All should share some keys (physics, introduction)
        common_keys = set.intersection(*all_keys)
        assert len(common_keys) > 0

        # Author variations
        author_variations = ["MacDonald, John", "McDonald, John", "John MacDonald", "John McDonald"]

        auth_keys = [generate_author_keys(author) for author in author_variations]
        # Should have some overlap (john, macdonald/mcdonald sound similar)
        for i in range(len(auth_keys)):
            for j in range(i + 1, len(auth_keys)):
                assert len(auth_keys[i] & auth_keys[j]) > 0
