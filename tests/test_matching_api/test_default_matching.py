"""Test the default matching implementations"""

# Third party imports
import pytest

# Local imports
from marc_pd_tool.default_matching import AdaptiveWeightingCombiner
from marc_pd_tool.default_matching import DefaultMatchingEngine
from marc_pd_tool.default_matching import DynamicWeightingCombiner
from marc_pd_tool.default_matching import FuzzyWuzzySimilarityCalculator
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
        score = self.calculator.calculate_title_similarity(
            "Completely Different", "Nothing Similar"
        )
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
        combined = self.combiner.combine_scores(80.0, 70.0, 90.0, marc_pub, copyright_pub, None)

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


class TestAdaptiveWeightingCombiner:
    """Test the adaptive weighting score combiner with weight redistribution"""

    def setup_method(self):
        """Set up test fixtures"""
        self.combiner = AdaptiveWeightingCombiner()
        self.generic_detector = GenericTitleDetector()

    def test_combine_scores_normal_with_complete_data(self):
        """Test score combination when all fields are present"""
        marc_pub = Publication("Specific Novel Title", "Smith, John", publisher="Penguin")
        copyright_pub = Publication("Specific Novel Title", "Smith, John", publisher="Penguin")

        # Normal title: title=60%, author=25%, publisher=15%
        combined = self.combiner.combine_scores(
            80.0, 70.0, 90.0, marc_pub, copyright_pub, self.generic_detector
        )

        expected = (80.0 * 0.6) + (70.0 * 0.25) + (90.0 * 0.15)  # 48 + 17.5 + 13.5 = 79
        assert combined == expected

    def test_combine_scores_marc_has_publisher_copyright_lacks(self):
        """Test weight redistribution when MARC has publisher but copyright record doesn't"""
        marc_pub = Publication("Specific Novel Title", "Smith, John", publisher="Penguin")
        copyright_pub = Publication("Specific Novel Title", "Smith, John")  # No publisher

        # Publisher is missing, so should redistribute 15% weight proportionally:
        # Original: title=60%, author=25%, publisher=15%
        # Remaining: title=60%, author=25% (total 85%)
        # New title weight: 60% + (60%/85% * 15%) = 60% + 10.59% = 70.59%
        # New author weight: 25% + (25%/85% * 15%) = 25% + 4.41% = 29.41%
        combined = self.combiner.combine_scores(
            80.0, 70.0, 90.0, marc_pub, copyright_pub, self.generic_detector
        )

        # Expected calculation with redistributed weights
        title_weight = 0.6 + (0.6 / 0.85 * 0.15)  # ≈ 0.7059
        author_weight = 0.25 + (0.25 / 0.85 * 0.15)  # ≈ 0.2941
        expected = (80.0 * title_weight) + (70.0 * author_weight)

        assert abs(combined - expected) < 0.01  # Allow small floating point differences

    def test_combine_scores_marc_lacks_publisher_copyright_has(self):
        """Test weight redistribution when copyright has publisher but MARC doesn't"""
        marc_pub = Publication("Specific Novel Title", "Smith, John")  # No publisher
        copyright_pub = Publication("Specific Novel Title", "Smith, John", publisher="Penguin")

        # Publisher is missing (MARC side), so should redistribute
        combined = self.combiner.combine_scores(
            80.0, 70.0, 90.0, marc_pub, copyright_pub, self.generic_detector
        )

        # Should use redistributed weights similar to previous test
        title_weight = 0.6 + (0.6 / 0.85 * 0.15)
        author_weight = 0.25 + (0.25 / 0.85 * 0.15)
        expected = (80.0 * title_weight) + (70.0 * author_weight)

        assert abs(combined - expected) < 0.01

    def test_combine_scores_both_lack_publisher(self):
        """Test score combination when both records lack publisher data"""
        marc_pub = Publication("Specific Novel Title", "Smith, John")
        copyright_pub = Publication("Specific Novel Title", "Smith, John")

        # Should use no-publisher scenario from config: title=70%, author=30%
        combined = self.combiner.combine_scores(
            80.0, 70.0, 90.0, marc_pub, copyright_pub, self.generic_detector
        )

        expected = (80.0 * 0.7) + (70.0 * 0.3)  # 56 + 21 = 77
        assert combined == expected

    def test_combine_scores_generic_with_redistribution(self):
        """Test weight redistribution with generic titles"""
        marc_pub = Publication("Complete Works", "Smith, John", publisher="Penguin")
        copyright_pub = Publication("Complete Works", "Smith, John")  # No publisher

        # Generic title missing publisher: original weights: title=30%, author=45%, publisher=25%
        # Redistribute 25% between title and author proportionally:
        # New title weight: 30% + (30%/75% * 25%) = 30% + 10% = 40%
        # New author weight: 45% + (45%/75% * 25%) = 45% + 15% = 60%
        combined = self.combiner.combine_scores(
            80.0, 70.0, 90.0, marc_pub, copyright_pub, self.generic_detector
        )

        title_weight = 0.3 + (0.3 / 0.75 * 0.25)  # = 0.3 + 0.1 = 0.4
        author_weight = 0.45 + (0.45 / 0.75 * 0.25)  # = 0.45 + 0.15 = 0.6
        expected = (80.0 * title_weight) + (70.0 * author_weight)  # 32 + 42 = 74

        assert abs(combined - expected) < 0.01

    def test_combine_scores_renewal_with_full_text(self):
        """Test that renewal records with full_text count as having publisher data"""
        marc_pub = Publication("Test Title", "Smith, John", publisher="Penguin")
        copyright_pub = Publication(
            "Test Title", "Smith, John", full_text="Published by Penguin Books in NY"
        )

        # Both have publisher-related data, should use with-publisher weights
        combined = self.combiner.combine_scores(
            80.0, 70.0, 90.0, marc_pub, copyright_pub, self.generic_detector
        )

        expected = (80.0 * 0.6) + (70.0 * 0.25) + (90.0 * 0.15)  # Normal with publisher
        assert combined == expected

    def test_detect_missing_fields_both_have_publisher(self):
        """Test that fields are correctly detected as present when both records have them"""
        marc_pub = Publication("Test Title", "Smith, John", publisher="Penguin")
        copyright_pub = Publication("Test Title", "Smith, John", publisher="Random House")

        missing = self.combiner._detect_missing_fields(marc_pub, copyright_pub)
        assert missing["publisher"] is False

    def test_detect_missing_fields_marc_missing(self):
        """Test that field is detected as missing when MARC lacks it"""
        marc_pub = Publication("Test Title", "Smith, John")  # No publisher
        copyright_pub = Publication("Test Title", "Smith, John", publisher="Penguin")

        missing = self.combiner._detect_missing_fields(marc_pub, copyright_pub)
        assert missing["publisher"] is True

    def test_detect_missing_fields_copyright_missing(self):
        """Test that field is detected as missing when copyright lacks it"""
        marc_pub = Publication("Test Title", "Smith, John", publisher="Penguin")
        copyright_pub = Publication("Test Title", "Smith, John")  # No publisher or full_text

        missing = self.combiner._detect_missing_fields(marc_pub, copyright_pub)
        assert missing["publisher"] is True

    def test_detect_missing_fields_renewal_full_text(self):
        """Test that renewal full_text counts as publisher data"""
        marc_pub = Publication("Test Title", "Smith, John", publisher="Penguin")
        copyright_pub = Publication("Test Title", "Smith, John", full_text="Some renewal text")

        missing = self.combiner._detect_missing_fields(marc_pub, copyright_pub)
        assert missing["publisher"] is False

    def test_redistribute_weights_single_missing_field(self):
        """Test weight redistribution calculation for one missing field"""
        original_weights = {"title": 0.6, "author": 0.25, "publisher": 0.15}
        missing_fields = {"publisher": True}

        new_weights = self.combiner._redistribute_weights(original_weights, missing_fields)

        # Should redistribute 0.15 proportionally between title (0.6) and author (0.25)
        # Total remaining: 0.85
        # Title gets: 0.6 + (0.6/0.85 * 0.15) ≈ 0.7059
        # Author gets: 0.25 + (0.25/0.85 * 0.15) ≈ 0.2941
        expected_title = 0.6 + (0.6 / 0.85 * 0.15)
        expected_author = 0.25 + (0.25 / 0.85 * 0.15)

        assert abs(new_weights["title"] - expected_title) < 0.001
        assert abs(new_weights["author"] - expected_author) < 0.001
        assert new_weights["publisher"] == 0.0

    def test_redistribute_weights_no_missing_fields(self):
        """Test that weights remain unchanged when no fields are missing"""
        original_weights = {"title": 0.6, "author": 0.25, "publisher": 0.15}
        missing_fields = {"publisher": False}

        new_weights = self.combiner._redistribute_weights(original_weights, missing_fields)

        assert new_weights == original_weights

    def test_combine_scores_comparison_with_dynamic_combiner(self):
        """Test that adaptive combiner produces higher scores than dynamic when fields are missing"""
        marc_pub = Publication("Test Title", "Smith, John", publisher="Penguin")
        copyright_pub = Publication("Test Title", "Smith, John")  # Missing publisher

        # Compare scores from both combiners
        adaptive_score = self.combiner.combine_scores(
            80.0, 70.0, 0.0, marc_pub, copyright_pub, self.generic_detector  # 0 publisher score
        )

        dynamic_combiner = DynamicWeightingCombiner()
        dynamic_score = dynamic_combiner.combine_scores(
            80.0, 70.0, 0.0, marc_pub, copyright_pub, self.generic_detector
        )

        # Adaptive should produce higher score since it redistributes the publisher weight
        assert adaptive_score > dynamic_score

        # Verify the specific scores
        # Dynamic: uses no-publisher weights (70%, 30%) = 80*0.7 + 70*0.3 = 56 + 21 = 77
        # Adaptive: redistributes from (60%, 25%, 15%) to (~70.6%, ~29.4%, 0%)
        #          = 80*0.706 + 70*0.294 ≈ 76.98
        assert abs(dynamic_score - 77.0) < 0.1
        assert adaptive_score > 76.9


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
        copyright_pub = Publication(
            "Test Title", "Smith, John", pub_date="1960"
        )  # 10 years difference

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
            pub_date="1950",
        )
        copyright_pub = Publication("Test Title", "Smith, John", pub_date="1950")

        result = self.engine.find_best_match(
            marc_pub,
            [copyright_pub],
            80,
            60,
            2,
            60,
            95,
            90,
            self.generic_detector,  # Lower author threshold
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
        copyright_pub = Publication(
            "Test Title", "Smith, John", publisher="Random House", pub_date="1950"
        )

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
            def combine_scores(
                self,
                title_score,
                author_score,
                publisher_score,
                marc_pub,
                copyright_pub,
                generic_detector=None,
            ):
                return 88.0  # Always return specific score

        engine = DefaultMatchingEngine(
            similarity_calculator=MockSimilarityCalculator(), score_combiner=MockScoreCombiner()
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
