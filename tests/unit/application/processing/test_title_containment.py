# tests/unit/application/processing/test_title_containment.py

"""Tests for title containment detection in Phase 2 improvements"""

# Third party imports
from pytest import fixture

# Local imports
from marc_pd_tool.application.processing.similarity_calculator import (
    SimilarityCalculator,
)
from marc_pd_tool.infrastructure.config import ConfigLoader


class TestTitleContainment:
    """Test title containment detection for subtitle and series handling"""

    @fixture
    def calculator(self):
        """Create similarity calculator"""
        config = ConfigLoader()
        return SimilarityCalculator(config)

    def test_exact_containment_at_start(self, calculator):
        """Test when shorter title is at the beginning of longer one"""
        # Case: Base title vs title with year
        score = calculator.calculate_title_similarity("Tax Guide", "Tax Guide 1934", "eng")
        assert score >= 85.0, "Should boost score for title + year pattern"

        # Case: Base title vs title with subtitle
        score = calculator.calculate_title_similarity(
            "Annual Report", "Annual Report of the Commissioner of Patents", "eng"
        )
        assert score >= 85.0, "Should boost score for title + subtitle pattern"

    def test_reverse_containment(self, calculator):
        """Test when longer title is in MARC and shorter in copyright"""
        score = calculator.calculate_title_similarity(
            "The Oxford English Dictionary Volume II", "Oxford English Dictionary", "eng"
        )
        assert score >= 75.0, "Should detect containment in reverse direction"

    def test_no_containment_boost_for_short_titles(self, calculator):
        """Test that very short titles don't get containment boost"""
        score = calculator.calculate_title_similarity("Tax", "Tax Guide", "eng")
        # Should use normal fuzzy matching, not containment
        assert score < 85.0, "Short titles shouldn't trigger containment boost"

    def test_series_volume_pattern(self, calculator):
        """Test common series/volume patterns"""
        score = calculator.calculate_title_similarity(
            "Deutsche Literatur",
            "Deutsche Literatur in Entwicklungsreihen Reihe Romantik Band 5",
            "eng",
        )
        assert score >= 75.0, "Should detect series name containment"

    def test_containment_with_punctuation(self, calculator):
        """Test containment with punctuation differences"""
        score = calculator.calculate_title_similarity(
            "Harper's Magazine", "Harper's Magazine: Volume 147", "eng"
        )
        assert score >= 85.0, "Should handle punctuation in containment"

    def test_no_false_containment(self, calculator):
        """Test that unrelated titles don't trigger containment"""
        score = calculator.calculate_title_similarity("The Great", "The Great Gatsby", "eng")
        # "The Great" is too generic and short
        assert score < 85.0, "Shouldn't boost generic partial matches"

        score = calculator.calculate_title_similarity(
            "Report", "Annual Report of the Treasury", "eng"
        )
        # "Report" alone is too generic
        assert score < 85.0, "Single generic words shouldn't trigger containment"

    def test_containment_with_stopwords(self, calculator):
        """Test containment detection after stopword removal"""
        # After normalization, these should still show containment
        score = calculator.calculate_title_similarity(
            "The Complete Works", "The Complete Works of William Shakespeare", "eng"
        )
        assert score >= 85.0, "Should detect containment even with stopwords"

    def test_containment_ratio_threshold(self, calculator):
        """Test that containment requires significant overlap"""
        # Small containment shouldn't trigger boost
        score = calculator.calculate_title_similarity(
            "New", "New York City Directory and Business Guide for 1934", "eng"
        )
        assert score < 85.0, "Minimal containment shouldn't trigger boost"

    def test_real_world_edge_cases(self, calculator):
        """Test real edge cases from the ground truth data"""
        # From edge case document: Commerce Clearing House pattern
        score = calculator.calculate_title_similarity(
            "Federal Tax Guide", "Federal Tax Guide 1934 with Latest Supplement", "eng"
        )
        assert score >= 85.0, "Should handle CCH tax guide pattern"

        # Academic series pattern
        score = calculator.calculate_title_similarity(
            "Harvard Studies", "Harvard Studies in Classical Philology Volume 42", "eng"
        )
        assert score >= 85.0, "Should handle academic series pattern"
