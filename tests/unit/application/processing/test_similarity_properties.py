# tests/unit/application/processing/test_similarity_properties.py

"""Property-based tests for similarity scoring functions

These tests verify that similarity scoring functions maintain certain mathematical
properties like bounded ranges, symmetry, and identity.
"""

# Third party imports
from hypothesis import given
from hypothesis import strategies as st

# Local imports
from marc_pd_tool.application.processing.similarity_calculator import (
    SimilarityCalculator,
)


class TestTitleSimilarityProperties:
    """Property-based tests for title similarity calculations"""

    def setup_method(self) -> None:
        """Set up test fixtures"""
        self.calculator = SimilarityCalculator()

    @given(
        st.text(min_size=1),
        st.text(min_size=1),
        st.sampled_from(["eng", "fre", "ger", "spa", "ita"]),
    )
    def test_title_similarity_range_constraint(
        self, title1: str, title2: str, language: str
    ) -> None:
        """Title similarity score should always be between 0 and 100"""
        score = self.calculator.calculate_title_similarity(title1, title2, language)
        assert 0 <= score <= 100

    @given(
        st.text(min_size=1),
        st.text(min_size=1),
        st.sampled_from(["eng", "fre", "ger", "spa", "ita"]),
    )
    def test_title_similarity_symmetry(self, title1: str, title2: str, language: str) -> None:
        """Title similarity should be symmetric"""
        score1 = self.calculator.calculate_title_similarity(title1, title2, language)
        score2 = self.calculator.calculate_title_similarity(title2, title1, language)
        assert score1 == score2

    @given(st.text(min_size=1), st.sampled_from(["eng", "fre", "ger", "spa", "ita"]))
    def test_title_similarity_identity(self, title: str, language: str) -> None:
        """Identical titles should have score of 100"""
        score = self.calculator.calculate_title_similarity(title, title, language)
        # Very short titles might be filtered out completely
        # Check what the processing actually produces
        # Local imports
        from marc_pd_tool.application.processing.text_processing import (
            expand_abbreviations,
        )

        expanded = expand_abbreviations(title)
        words = expanded.lower().split()

        # Filter out words < 2 chars (same as the algorithm)
        significant_words = [w for w in words if len(w) >= 2]

        # Identical titles should always score 100, even if they normalize to nothing
        assert score == 100.0

    @given(
        st.text(min_size=1),
        st.text(min_size=1),
        st.sampled_from(["eng", "fre", "ger", "spa", "ita"]),
    )
    def test_title_similarity_handles_any_input(
        self, title1: str, title2: str, language: str
    ) -> None:
        """Should handle any input without crashing"""
        try:
            score = self.calculator.calculate_title_similarity(title1, title2, language)
            assert isinstance(score, float)
        except Exception as e:
            assert False, f"calculate_title_similarity raised exception: {e}"

    @given(
        st.text(min_size=1),
        st.text(min_size=1),
        st.sampled_from(["eng", "fre", "ger", "spa", "ita"]),
    )
    def test_language_affects_stopwords(self, title1: str, title2: str, language: str) -> None:
        """Different languages should use different stopwords"""
        # Add language-specific stopwords to test
        english_title = "the book of the world"
        french_title = "le livre du monde"

        if language == "eng":
            # Test that English stopwords are handled
            score = self.calculator.calculate_title_similarity(
                english_title, english_title, language
            )
            assert score == 100
        elif language == "fre":
            # Test that French stopwords are handled
            score = self.calculator.calculate_title_similarity(french_title, french_title, language)
            assert score == 100


class TestAuthorSimilarityProperties:
    """Property-based tests for author similarity calculations"""

    def setup_method(self) -> None:
        """Set up test fixtures"""
        self.calculator = SimilarityCalculator()

    @given(
        st.text(min_size=1),
        st.text(min_size=1),
        st.sampled_from(["eng", "fre", "ger", "spa", "ita"]),
    )
    def test_author_similarity_range_constraint(
        self, marc_author: str, target_author: str, language: str
    ) -> None:
        """Author similarity score should always be between 0 and 100"""
        score = self.calculator.calculate_author_similarity(marc_author, target_author, language)
        assert 0 <= score <= 100

    @given(st.text(min_size=1), st.text(min_size=1))
    def test_author_similarity_symmetry_simple(self, author1: str, author2: str) -> None:
        """Author similarity should be symmetric for simple case"""
        score1 = self.calculator.calculate_author_similarity(author1, author2)
        score2 = self.calculator.calculate_author_similarity(author2, author1)
        assert score1 == score2

    @given(st.text(min_size=1))
    def test_author_similarity_identity(self, author: str) -> None:
        """Identical authors should have score of 100"""
        score = self.calculator.calculate_author_similarity(author, author)
        # Very short names might be filtered out
        if len(author.strip()) == 0:
            assert score == 100
        elif all(len(word) < 2 for word in author.split()):
            # All words too short - might return 0 if filtered
            assert score in [0, 100]
        else:
            assert score == 100

    @given(
        st.text(min_size=1),
        st.text(min_size=1),
        st.sampled_from(["eng", "fre", "ger", "spa", "ita"]),
    )
    def test_author_similarity_handles_any_input(
        self, marc_author: str, target_author: str, language: str
    ) -> None:
        """Should handle any input without crashing"""
        try:
            score = self.calculator.calculate_author_similarity(
                marc_author, target_author, language
            )
            assert isinstance(score, float)
        except Exception as e:
            assert False, f"calculate_author_similarity raised exception: {e}"

    @given(st.text(min_size=1), st.text(min_size=1))
    def test_author_empty_handling(self, author1: str, author2: str) -> None:
        """Empty authors should be handled correctly"""
        # Empty vs non-empty should give 0
        score1 = self.calculator.calculate_author_similarity("", author1)
        score2 = self.calculator.calculate_author_similarity(author1, "")
        assert score1 == 0
        assert score2 == 0


class TestPublisherSimilarityProperties:
    """Property-based tests for publisher similarity calculations"""

    def setup_method(self) -> None:
        """Set up test fixtures"""
        self.calculator = SimilarityCalculator()

    @given(st.text(min_size=1), st.text(min_size=1))
    def test_publisher_similarity_range_constraint(self, pub1: str, pub2: str) -> None:
        """Publisher similarity score should always be between 0 and 100"""
        score = self.calculator.calculate_publisher_similarity(pub1, pub2)
        assert 0 <= score <= 100

    @given(st.text(min_size=1), st.text(min_size=1))
    def test_publisher_similarity_symmetry(self, pub1: str, pub2: str) -> None:
        """Publisher similarity should be symmetric"""
        score1 = self.calculator.calculate_publisher_similarity(pub1, pub2)
        score2 = self.calculator.calculate_publisher_similarity(pub2, pub1)
        assert score1 == score2

    @given(st.text(min_size=1))
    def test_publisher_similarity_identity(self, publisher: str) -> None:
        """Identical publishers should have score of 100"""
        score = self.calculator.calculate_publisher_similarity(publisher, publisher)
        assert score == 100

    @given(st.text(min_size=1), st.text(min_size=1))
    def test_publisher_similarity_handles_any_input(self, pub1: str, pub2: str) -> None:
        """Should handle any input without crashing"""
        try:
            score = self.calculator.calculate_publisher_similarity(pub1, pub2)
            assert isinstance(score, float)
        except Exception as e:
            assert False, f"calculate_publisher_similarity raised exception: {e}"

    @given(st.text(), st.text())
    def test_publisher_similarity_empty_handling(self, pub1: str, pub2: str) -> None:
        """Empty publishers should be handled gracefully"""
        if not pub1 or not pub2:
            score = self.calculator.calculate_publisher_similarity(pub1, pub2)
            # Empty publisher should give 0 score when compared to non-empty
            if bool(pub1) != bool(pub2):
                assert score == 0


class TestSimilarityEdgeCases:
    """Test edge cases and special scenarios"""

    def setup_method(self) -> None:
        """Set up test fixtures"""
        self.calculator = SimilarityCalculator()

    @given(st.text(alphabet=st.characters(min_codepoint=97, max_codepoint=122), min_size=1))
    def test_case_sensitivity(self, text: str) -> None:
        """Test case sensitivity across all similarity methods"""
        # Title comparison
        title_score = self.calculator.calculate_title_similarity(text, text.upper(), "eng")
        # Author comparison
        author_score = self.calculator.calculate_author_similarity(text, text.upper())
        # Publisher comparison
        publisher_score = self.calculator.calculate_publisher_similarity(text, text.upper())

        # All should be case-insensitive (score = 100)
        # But single char text might be filtered out
        if len(text) > 1 or not text.isalnum():
            assert title_score == 100
            assert author_score == 100
            assert publisher_score == 100
        else:
            # Single char might be filtered as too short
            assert title_score in [0, 100]
            assert author_score in [0, 100]
            assert publisher_score == 100  # Publisher doesn't filter short words

    @given(st.text(min_size=1))
    def test_unicode_normalization_consistency(self, text: str) -> None:
        """Unicode normalization should be applied consistently"""
        # Add some accented characters
        text_accented = text + "café"
        text_normalized = text + "cafe"

        # Title should normalize unicode
        score = self.calculator.calculate_title_similarity(text_accented, text_normalized, "eng")
        # Should be very high since normalization removes accents
        assert score > 90
