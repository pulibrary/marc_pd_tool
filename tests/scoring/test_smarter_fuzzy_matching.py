# tests/scoring/test_smarter_fuzzy_matching.py

"""Test Phase 4B: Smarter Fuzzy Matching to reduce false positives"""

# Third party imports
from pytest import fixture

# Local imports
from marc_pd_tool.application.processing.similarity_calculator import (
    SimilarityCalculator,
)


class TestSmarterFuzzyMatching:
    """Test Phase 4B: Smarter fuzzy matching to reduce false positives"""

    @fixture
    def calculator(self) -> SimilarityCalculator:
        """Create a SimilarityCalculator instance"""
        return SimilarityCalculator()

    def test_single_word_match_capped(self, calculator: SimilarityCalculator):
        """Test that single distinctive word matches are capped appropriately"""
        # After stopword removal, only one distinctive word remains
        # Example: "The Book" vs "The Novel" - only distinctive words are "book" and "novel"
        score = calculator.calculate_title_similarity("Annual Report", "Annual Review", "eng")

        # Refined: Allow up to 60 for short titles with single-word overlap
        # This was changed to maintain better true positive rate
        assert score <= 60, f"Single word match should cap at 60 for short titles, got {score}"

    def test_low_word_overlap_penalty(self, calculator: SimilarityCalculator):
        """Test penalty when word overlap is low

        Example: "War over England" vs "English literature"
        """
        score = calculator.calculate_title_similarity(
            "War over England", "English literature", "eng"
        )

        # Should be much lower than before due to poor word overlap
        assert score < 40, f"Low overlap should score <40, got {score}"

    def test_stem_only_match_penalty(self, calculator: SimilarityCalculator):
        """Test penalty when only stems match but not original words

        Example: England/English stem similarity
        """
        score = calculator.calculate_title_similarity(
            "History of England", "English History", "eng"
        )

        # Despite similar meaning, stems matching better than originals
        # should trigger penalty
        assert score < 70, f"Stem-only similarity should be penalized, got {score}"

    def test_short_title_penalty(self, calculator: SimilarityCalculator):
        """Test penalty for very short titles after normalization"""
        score = calculator.calculate_title_similarity("War", "Peace", "eng")

        # Single words, completely different - should score very low
        assert score == 0, f"Different single words should score 0, got {score}"

    def test_common_words_dont_inflate(self, calculator: SimilarityCalculator):
        """Test that common words don't inflate scores"""
        # Titles share common words but are unrelated
        score = calculator.calculate_title_similarity(
            "The History of the United States", "The Story of the American Revolution", "eng"
        )

        # Despite sharing "the" and having some overlap, should score lower
        assert score < 50, f"Common words shouldn't inflate score >50, got {score}"

    def test_genuine_match_not_overly_penalized(self, calculator: SimilarityCalculator):
        """Test that genuine matches aren't hurt by stricter matching"""
        # Legitimate variations of the same work
        score = calculator.calculate_title_similarity(
            "Introduction to Computer Science", "Intro to Computer Sciences", "eng"
        )

        # Should still score high despite abbreviation and plural
        assert score > 80, f"Genuine match should score >80, got {score}"

    def test_good_word_overlap_scores_well(self, calculator: SimilarityCalculator):
        """Test that good word overlap still scores well"""
        score = calculator.calculate_title_similarity(
            "Modern American Literature", "American Modern Literature", "eng"
        )

        # Same words, different order - should score very high
        assert score > 90, f"Good overlap should score >90, got {score}"

    def test_empty_after_stopwords_handled(self, calculator: SimilarityCalculator):
        """Test handling when text becomes empty after stopword removal"""
        # If both normalize to nothing (all stopwords)
        score = calculator.calculate_title_similarity("The", "The", "eng")

        # Identical stopwords should match
        assert score == 100, f"Identical stopwords should score 100, got {score}"

        # Different stopwords shouldn't match
        score2 = calculator.calculate_title_similarity("The", "And", "eng")
        assert score2 == 0, f"Different stopwords should score 0, got {score2}"

    def test_partial_overlap_with_penalty(self, calculator: SimilarityCalculator):
        """Test that partial word overlap gets appropriate penalty"""
        # Some words match but not enough for confidence
        score = calculator.calculate_title_similarity(
            "Advanced Database Systems", "Database Management Basics", "eng"
        )

        # Only "Database" really overlaps - should be penalized
        assert score < 60, f"Partial overlap should score <60, got {score}"

    def test_known_false_positive_examples(self, calculator: SimilarityCalculator):
        """Test actual false positive examples from the dataset"""
        # Example 1: "Mary Magdalen" vs "dark canyon"
        score1 = calculator.calculate_title_similarity("Mary Magdalen", "dark canyon", "eng")
        assert score1 < 30, f"'Mary Magdalen' vs 'dark canyon' should score <30, got {score1}"

        # Example 2: "Fellow creatures" vs "literature and society"
        score2 = calculator.calculate_title_similarity(
            "Fellow creatures", "literature and society", "eng"
        )
        assert (
            score2 < 30
        ), f"'Fellow creatures' vs 'literature and society' should score <30, got {score2}"

        # Example 3: "The Island, a love story" vs "les meres coupable"
        score3 = calculator.calculate_title_similarity(
            "The Island, a love story", "les meres coupable villesavoye boisleve", "eng"
        )
        assert score3 < 30, f"'The Island' vs 'les meres' should score <30, got {score3}"
