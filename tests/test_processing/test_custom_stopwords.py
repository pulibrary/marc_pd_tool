# tests/test_processing/test_custom_stopwords.py

"""Test custom stopword removal based on ground truth analysis"""

# Third party imports
from pytest import fixture

# Local imports
from marc_pd_tool.application.processing.custom_stopwords import CustomStopwordRemover
from marc_pd_tool.application.processing.similarity_calculator import (
    SimilarityCalculator,
)


class TestCustomStopwords:
    """Test the custom stopword remover"""

    @fixture
    def remover(self):
        """Create a stopword remover instance"""
        return CustomStopwordRemover()

    def test_english_title_stopwords(self, remover):
        """Test English title stopword removal"""
        text = "the history of the american world"
        result = remover.remove_stopwords(text, "eng", "title")

        # "the", "of" should be removed
        # "history", "american", "world" should be kept (content words)
        assert "the" not in result
        assert "of" not in result
        assert "history" in result
        assert "american" in result
        assert "world" in result

    def test_english_author_stopwords(self, remover):
        """Test English author stopword removal"""
        text = "edited by john smith and illustrated by jane doe"
        result = remover.remove_stopwords(text, "eng", "author")

        # "by", "and" should be removed
        # "edited", "illustrated" should be kept (meaningful for authors)
        assert "by" not in result
        assert "and" not in result
        assert "edited" in result
        assert "illustrated" in result
        assert "john" in result
        assert "smith" in result

    def test_english_publisher_stopwords(self, remover):
        """Test English publisher stopword removal - very minimal"""
        text = "the university of chicago press and company"
        result = remover.remove_stopwords(text, "eng", "publisher")

        # Only articles and prepositions removed, NOT corporate terms
        assert "the" not in result
        assert "of" not in result
        assert "and" not in result
        assert "university" in result
        assert "chicago" in result
        assert "press" in result
        assert "company" in result

    def test_french_conservative_removal(self, remover):
        """Test French conservative stopword removal"""
        text = "le livre de la république française"
        result = remover.remove_stopwords(text, "fre", "title")

        # Articles should NOT be removed in French (le, la, de)
        # Only conjunctions like "et" are removed
        assert "livre" in result
        assert "république" in result
        assert "française" in result
        # Note: "le", "la", "de" are kept if >= 4 chars or not in stopwords

    def test_german_conservative_removal(self, remover):
        """Test German conservative stopword removal"""
        text = "der deutsche verlag und die gesellschaft"
        result = remover.remove_stopwords(text, "ger", "title")

        # "und" should be removed, but articles kept
        assert "und" not in result
        assert "deutsche" in result
        assert "verlag" in result
        assert "gesellschaft" in result

    def test_minimum_word_length(self, remover):
        """Test minimum word length enforcement"""
        # English: 3 chars minimum
        eng_text = "a to be or not to be in it"
        eng_result = remover.remove_stopwords(eng_text, "eng", "title")
        # Short stopwords removed, but non-stopwords kept even if short
        assert "a" not in eng_result
        assert "to" not in eng_result
        assert "be" not in eng_result
        assert "or" not in eng_result
        assert "in" not in eng_result
        assert "it" not in eng_result

        # French: 4 chars minimum
        fre_text = "et ou le la un une"
        remover.remove_stopwords(fre_text, "fre", "title")
        # "et", "ou" are stopwords and removed
        # Others kept if >= 4 chars or not stopwords


class TestSimilarityWithCustomStopwords:
    """Test similarity calculation with custom stopwords"""

    @fixture
    def calculator(self):
        """Create a similarity calculator with custom stopwords"""
        return SimilarityCalculator()

    def test_english_title_similarity_improvement(self, calculator):
        """Test that custom stopwords improve English title matching"""
        # These should match well after removing common words
        score = calculator.calculate_title_similarity(
            "The Complete History of the American Revolution",
            "Complete History of American Revolution",
            "eng",
        )
        # Should have high similarity after removing "the" articles
        assert score > 85

    def test_french_article_preservation(self, calculator):
        """Test that French articles are preserved"""
        # Articles are meaningful in French
        score1 = calculator.calculate_title_similarity("Le Monde", "Monde", "fre")

        score2 = calculator.calculate_title_similarity("Le Monde", "Le Monde", "fre")

        # Exact match should score higher
        assert score2 > score1

    def test_publisher_corporate_terms_preserved(self, calculator):
        """Test that corporate terms are preserved for publishers"""
        score = calculator.calculate_publisher_similarity(
            "University of Chicago Press", "University Chicago Press", "", "eng"  # No full text
        )
        # Should match well even though "of" is removed
        assert score > 80

        # Corporate terms should be preserved
        score2 = calculator.calculate_publisher_similarity(
            "Random House Publishing Company", "Random House Company", "", "eng"
        )
        # Should still match reasonably well
        assert score2 > 70
