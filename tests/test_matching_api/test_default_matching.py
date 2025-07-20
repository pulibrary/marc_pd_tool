"""Test the default matching implementations"""

import pytest

from marc_pd_tool.default_matching import (
    DefaultMatchingEngine,
    DynamicWeightingCombiner,
    FuzzyWuzzySimilarityCalculator,
)
from marc_pd_tool.generic_title_detector import GenericTitleDetector
from marc_pd_tool.publication import Publication


class TestFuzzyWuzzySimilarityCalculator:
    """Test the default fuzzywuzzy-based similarity calculator"""

    def setup_method(self):
        """Set up test fixtures"""
        self.calculator = FuzzyWuzzySimilarityCalculator()

    def test_calculate_title_similarity(self):
        """Test title similarity calculation"""
        # Exact match should be 100
        assert self.calculator.calculate_title_similarity("Test Title", "Test Title") == 100.0
        
        # Partial match should be between 0 and 100
        score = self.calculator.calculate_title_similarity("Test Title", "Test Book")
        assert 0 < score < 100
        
        # No match should be low
        score = self.calculator.calculate_title_similarity("Completely Different", "Nothing Similar")
        assert score < 50

    def test_calculate_author_similarity(self):
        """Test author similarity calculation"""
        # Exact match should be 100
        assert self.calculator.calculate_author_similarity("Smith, John", "Smith, John") == 100.0
        
        # Similar names should score well
        score = self.calculator.calculate_author_similarity("Smith, John", "Smith, J.")
        assert score > 70
        
        # Different names should score low
        score = self.calculator.calculate_author_similarity("Smith, John", "Doe, Jane")
        assert score < 50

    def test_calculate_publisher_similarity_direct(self):
        """Test publisher similarity with direct comparison"""
        # Exact match
        score = self.calculator.calculate_publisher_similarity("Penguin Books", "Penguin Books", "")
        assert score == 100.0
        
        # Partial match
        score = self.calculator.calculate_publisher_similarity("Penguin", "Penguin Books", "")
        assert 50 < score < 100
        
        # No match
        score = self.calculator.calculate_publisher_similarity("Penguin", "Random House", "")
        assert score < 50

    def test_calculate_publisher_similarity_full_text(self):
        """Test publisher similarity with full text matching"""
        # Publisher found in full text
        score = self.calculator.calculate_publisher_similarity(
            "Penguin", "", "This book was published by Penguin Books in New York"
        )
        assert score > 70
        
        # Publisher not found in full text
        score = self.calculator.calculate_publisher_similarity(
            "Random House", "", "This book was published by Penguin Books in New York"
        )
        assert score < 50

    def test_calculate_publisher_similarity_no_data(self):
        """Test publisher similarity when no publisher data is available"""
        score = self.calculator.calculate_publisher_similarity("Penguin", "", "")
        assert score == 0.0


class TestDynamicWeightingCombiner:
    """Test the dynamic weighting score combiner"""

    def setup_method(self):
        """Set up test fixtures"""
        self.combiner = DynamicWeightingCombiner()
        self.generic_detector = GenericTitleDetector()

    def test_combine_scores_normal_with_publisher(self):
        """Test score combination for normal titles with publisher data"""
        marc_pub = Publication("Specific Novel Title", "Smith, John", publisher="Penguin")
        copyright_pub = Publication("Specific Novel Title", "Smith, John", publisher="Penguin")
        
        # Normal title: title=60%, author=25%, publisher=15%
        combined = self.combiner.combine_scores(
            80.0, 70.0, 90.0, marc_pub, copyright_pub, self.generic_detector
        )
        
        expected = (80.0 * 0.6) + (70.0 * 0.25) + (90.0 * 0.15)  # 48 + 17.5 + 13.5 = 79
        assert combined == expected

    def test_combine_scores_generic_with_publisher(self):
        """Test score combination for generic titles with publisher data"""
        marc_pub = Publication("Complete Works", "Smith, John", publisher="Penguin")
        copyright_pub = Publication("Complete Works", "Smith, John", publisher="Penguin")
        
        # Generic title: title=30%, author=45%, publisher=25%
        combined = self.combiner.combine_scores(
            80.0, 70.0, 90.0, marc_pub, copyright_pub, self.generic_detector
        )
        
        expected = (80.0 * 0.3) + (70.0 * 0.45) + (90.0 * 0.25)  # 24 + 31.5 + 22.5 = 78
        assert combined == expected

    def test_combine_scores_normal_without_publisher(self):
        """Test score combination for normal titles without publisher data"""
        marc_pub = Publication("Specific Novel Title", "Smith, John")
        copyright_pub = Publication("Specific Novel Title", "Smith, John")
        
        # Normal title, no publisher: title=70%, author=30%
        combined = self.combiner.combine_scores(
            80.0, 70.0, 90.0, marc_pub, copyright_pub, self.generic_detector
        )
        
        expected = (80.0 * 0.7) + (70.0 * 0.3)  # 56 + 21 = 77
        assert combined == expected

    def test_combine_scores_generic_without_publisher(self):
        """Test score combination for generic titles without publisher data"""
        marc_pub = Publication("Poems", "Smith, John")
        copyright_pub = Publication("Poems", "Smith, John")
        
        # Generic title, no publisher: title=40%, author=60%
        combined = self.combiner.combine_scores(
            80.0, 70.0, 90.0, marc_pub, copyright_pub, self.generic_detector
        )
        
        expected = (80.0 * 0.4) + (70.0 * 0.6)  # 32 + 42 = 74
        assert combined == expected

    def test_combine_scores_without_generic_detector(self):
        """Test score combination when no generic detector is provided"""
        marc_pub = Publication("Complete Works", "Smith, John", publisher="Penguin")
        copyright_pub = Publication("Complete Works", "Smith, John", publisher="Penguin")
        
        # Should default to normal weighting without generic detection
        combined = self.combiner.combine_scores(
            80.0, 70.0, 90.0, marc_pub, copyright_pub, None
        )
        
        expected = (80.0 * 0.6) + (70.0 * 0.25) + (90.0 * 0.15)  # Normal weighting
        assert combined == expected

    def test_combine_scores_marc_only_has_publisher(self):
        """Test when only MARC record has publisher data"""
        marc_pub = Publication("Test Title", "Smith, John", publisher="Penguin")
        copyright_pub = Publication("Test Title", "Smith, John")  # No publisher
        
        # Should use no-publisher weighting since copyright_pub has no publisher/full_text
        combined = self.combiner.combine_scores(
            80.0, 70.0, 90.0, marc_pub, copyright_pub, self.generic_detector
        )
        
        expected = (80.0 * 0.7) + (70.0 * 0.3)  # No publisher weighting
        assert combined == expected


class TestDefaultMatchingEngine:
    """Test the default matching engine implementation"""

    def setup_method(self):
        """Set up test fixtures"""
        self.engine = DefaultMatchingEngine()
        self.generic_detector = GenericTitleDetector()

    def test_find_best_match_exact_match(self):
        """Test finding exact match"""
        marc_pub = Publication("Test Title", "Smith, John", pub_date="1950")
        copyright_pub = Publication("Test Title", "Smith, John", pub_date="1950")
        
        result = self.engine.find_best_match(
            marc_pub, [copyright_pub], 80, 70, 2, 60, 95, 90, self.generic_detector
        )
        
        assert result is not None
        assert result["similarity_scores"]["title"] == 100.0
        assert result["similarity_scores"]["combined"] > 90

    def test_find_best_match_no_match(self):
        """Test when no match is found"""
        marc_pub = Publication("Test Title", "Smith, John", pub_date="1950")
        copyright_pub = Publication("Completely Different", "Doe, Jane", pub_date="1951")
        
        result = self.engine.find_best_match(
            marc_pub, [copyright_pub], 80, 70, 2, 60, 95, 90, self.generic_detector
        )
        
        assert result is None

    def test_find_best_match_year_filtering(self):
        """Test that year filtering works correctly"""
        marc_pub = Publication("Test Title", "Smith, John", pub_date="1950")
        copyright_pub = Publication("Test Title", "Smith, John", pub_date="1960")  # 10 years difference
        
        # With year_tolerance=2, should not match
        result = self.engine.find_best_match(
            marc_pub, [copyright_pub], 80, 70, 2, 60, 95, 90, self.generic_detector
        )
        assert result is None
        
        # With year_tolerance=15, should match
        result = self.engine.find_best_match(
            marc_pub, [copyright_pub], 80, 70, 15, 60, 95, 90, self.generic_detector
        )
        assert result is not None

    def test_find_best_match_dual_author_scoring(self):
        """Test that dual author scoring works correctly"""
        marc_pub = Publication(
            "Test Title", 
            author="by John Smith",  # 245$c transcribed
            main_author="Smith, John",  # 1xx normalized (removed dates for better matching)
            pub_date="1950"
        )
        copyright_pub = Publication("Test Title", "Smith, John", pub_date="1950")
        
        result = self.engine.find_best_match(
            marc_pub, [copyright_pub], 80, 60, 2, 60, 95, 90, self.generic_detector  # Lower author threshold
        )
        
        assert result is not None
        # Should get high author score from either 245$c or 1xx field
        assert result["similarity_scores"]["author"] >= 60

    def test_find_best_match_title_threshold(self):
        """Test that title threshold filtering works"""
        marc_pub = Publication("Test Title", "Smith, John", pub_date="1950")
        copyright_pub = Publication("Somewhat Similar", "Smith, John", pub_date="1950")
        
        # With high title threshold, should not match
        result = self.engine.find_best_match(
            marc_pub, [copyright_pub], 90, 70, 2, 60, 95, 90, self.generic_detector
        )
        assert result is None
        
        # With low title threshold, should match
        result = self.engine.find_best_match(
            marc_pub, [copyright_pub], 30, 70, 2, 60, 95, 90, self.generic_detector
        )
        assert result is not None

    def test_find_best_match_early_exit(self):
        """Test that early exit works with high-confidence matches"""
        marc_pub = Publication("Test Title", "Smith, John", pub_date="1950")
        
        # Create multiple candidates, exact match first
        exact_match = Publication("Test Title", "Smith, John", pub_date="1950")
        other_match = Publication("Test Title", "Smith, John", pub_date="1951")
        
        result = self.engine.find_best_match(
            marc_pub, [exact_match, other_match], 80, 70, 2, 60, 95, 90, self.generic_detector
        )
        
        assert result is not None
        # Should find the exact match (first one due to early exit)
        assert result["similarity_scores"]["title"] == 100.0
        assert result["similarity_scores"]["author"] == 100.0

    def test_find_best_match_publisher_threshold(self):
        """Test that publisher threshold works when MARC has publisher data"""
        marc_pub = Publication("Test Title", "Smith, John", publisher="Penguin", pub_date="1950")
        copyright_pub = Publication("Test Title", "Smith, John", publisher="Random House", pub_date="1950")
        
        # With high publisher threshold, should not match due to different publishers
        result = self.engine.find_best_match(
            marc_pub, [copyright_pub], 80, 70, 2, 90, 95, 90, self.generic_detector
        )
        assert result is None
        
        # With low publisher threshold, should match
        result = self.engine.find_best_match(
            marc_pub, [copyright_pub], 80, 70, 2, 10, 95, 90, self.generic_detector
        )
        assert result is not None

    def test_find_best_match_custom_components(self):
        """Test that custom similarity calculator and score combiner work"""
        
        class MockSimilarityCalculator(FuzzyWuzzySimilarityCalculator):
            def calculate_title_similarity(self, marc_title: str, copyright_title: str) -> float:
                return 95.0  # Always return high score
            
            def calculate_author_similarity(self, marc_author: str, copyright_author: str) -> float:
                return 85.0  # Always return high author score
        
        class MockScoreCombiner(DynamicWeightingCombiner):
            def combine_scores(self, title_score, author_score, publisher_score, marc_pub, copyright_pub, generic_detector=None):
                return 88.0  # Always return specific score
        
        engine = DefaultMatchingEngine(
            similarity_calculator=MockSimilarityCalculator(),
            score_combiner=MockScoreCombiner()
        )
        
        marc_pub = Publication("Test Title", "Smith, John", pub_date="1950")
        copyright_pub = Publication("Different Title", "Doe, Jane", pub_date="1950")
        
        result = engine.find_best_match(
            marc_pub, [copyright_pub], 80, 70, 2, 60, 95, 90, self.generic_detector
        )
        
        assert result is not None
        assert result["similarity_scores"]["title"] == 95.0
        assert result["similarity_scores"]["author"] == 85.0
        assert result["similarity_scores"]["combined"] == 88.0

    def test_find_best_match_generic_title_info(self):
        """Test that generic title detection info is included in results"""
        marc_pub = Publication("Complete Works", "Smith, John", pub_date="1950")  # Generic title
        copyright_pub = Publication("Complete Works", "Smith, John", pub_date="1950")
        
        result = self.engine.find_best_match(
            marc_pub, [copyright_pub], 80, 70, 2, 60, 95, 90, self.generic_detector
        )
        
        assert result is not None
        assert "generic_title_info" in result
        assert result["generic_title_info"]["has_generic_title"] is True
        assert result["generic_title_info"]["marc_title_is_generic"] is True