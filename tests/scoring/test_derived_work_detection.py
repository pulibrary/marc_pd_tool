# tests/scoring/test_derived_work_detection.py

"""Test Phase 5: Derived Work Detection to prevent false positives"""

# Third party imports
from pytest import fixture

# Local imports
from marc_pd_tool.application.processing.derived_work_detector import (
    DerivedWorkDetector,
)
from marc_pd_tool.application.processing.derived_work_detector import DerivedWorkInfo
from marc_pd_tool.application.processing.matching._score_combiner import ScoreCombiner
from marc_pd_tool.infrastructure.config import ConfigLoader


class TestDerivedWorkDetection:
    """Test Phase 5: Detection of indexes, bibliographies, supplements, etc."""

    @fixture
    def detector(self) -> DerivedWorkDetector:
        """Create a DerivedWorkDetector instance"""
        return DerivedWorkDetector()

    @fixture
    def score_combiner(self) -> ScoreCombiner:
        """Create a ScoreCombiner instance"""
        config = ConfigLoader()
        return ScoreCombiner(config)

    def test_index_detection_english(self, detector: DerivedWorkDetector):
        """Test detection of English index patterns"""
        # "Index to" pattern
        marc_info, copyright_info = detector.detect(
            "Index to War and Peace", "War and Peace", "eng"
        )

        assert marc_info.is_derived is True
        assert marc_info.pattern_matched == "index"
        assert marc_info.confidence == 0.95
        assert copyright_info.is_derived is False

        # "Index of" pattern
        marc_info2, copyright_info2 = detector.detect(
            "Poetry Today", "Index of Poetry Today", "eng"
        )

        assert marc_info2.is_derived is False
        assert copyright_info2.is_derived is True
        assert copyright_info2.pattern_matched == "index"

    def test_bibliography_detection(self, detector: DerivedWorkDetector):
        """Test detection of bibliography patterns"""
        marc_info, copyright_info = detector.detect(
            "Bibliography of American Literature", "American Literature", "eng"
        )

        assert marc_info.is_derived is True
        assert marc_info.pattern_matched == "bibliography"
        assert marc_info.confidence == 0.95
        assert copyright_info.is_derived is False

    def test_supplement_detection(self, detector: DerivedWorkDetector):
        """Test detection of supplement patterns"""
        marc_info, copyright_info = detector.detect(
            "Chemistry Handbook", "Supplement to Chemistry Handbook", "eng"
        )

        assert marc_info.is_derived is False
        assert copyright_info.is_derived is True
        assert copyright_info.pattern_matched == "supplement"
        assert copyright_info.confidence == 0.9

    def test_french_patterns(self, detector: DerivedWorkDetector):
        """Test detection of French derived work patterns"""
        # Index
        marc_info, copyright_info = detector.detect(
            "Index de la littérature française", "La littérature française", "fre"
        )
        assert marc_info.is_derived is True
        assert marc_info.pattern_matched == "index"

        # Bibliographie
        marc_info2, copyright_info2 = detector.detect(
            "Histoire de France", "Bibliographie de l'histoire de France", "fre"
        )
        assert copyright_info2.is_derived is True
        assert copyright_info2.pattern_matched == "bibliographie"

        # Supplément
        marc_info3, copyright_info3 = detector.detect(
            "Supplément au dictionnaire", "Dictionnaire français", "fre"
        )
        assert marc_info3.is_derived is True
        assert marc_info3.pattern_matched == "supplement"

    def test_german_patterns(self, detector: DerivedWorkDetector):
        """Test detection of German derived work patterns"""
        # Register (index)
        marc_info, copyright_info = detector.detect(
            "Register zu Goethes Werken", "Goethes Werke", "ger"
        )
        assert marc_info.is_derived is True
        assert marc_info.pattern_matched == "register"

        # Ergänzung (supplement)
        marc_info2, copyright_info2 = detector.detect(
            "Deutsche Geschichte", "Ergänzung zur Deutschen Geschichte", "ger"
        )
        assert copyright_info2.is_derived is True
        assert copyright_info2.pattern_matched == "ergaenzung"

    def test_spanish_patterns(self, detector: DerivedWorkDetector):
        """Test detection of Spanish derived work patterns"""
        # Índice
        marc_info, copyright_info = detector.detect(
            "Índice de literatura española", "Literatura española", "spa"
        )
        assert marc_info.is_derived is True
        assert marc_info.pattern_matched == "indice"

        # Bibliografía
        marc_info2, copyright_info2 = detector.detect(
            "Historia de España", "Bibliografía sobre historia de España", "spa"
        )
        assert copyright_info2.is_derived is True
        assert copyright_info2.pattern_matched == "bibliografia"

    def test_italian_patterns(self, detector: DerivedWorkDetector):
        """Test detection of Italian derived work patterns"""
        # Indice
        marc_info, copyright_info = detector.detect(
            "Indice di letteratura italiana", "Letteratura italiana", "ita"
        )
        assert marc_info.is_derived is True
        assert marc_info.pattern_matched == "indice"

    def test_suffix_patterns(self, detector: DerivedWorkDetector):
        """Test detection of suffix patterns (e.g., '... index')"""
        marc_info, copyright_info = detector.detect(
            "American History Index", "American History", "eng"
        )

        assert marc_info.is_derived is True
        assert marc_info.pattern_matched == "index_suffix"
        assert marc_info.confidence == 0.9

    def test_cross_language_detection(self, detector: DerivedWorkDetector):
        """Test that English patterns are checked even for other languages"""
        # English index pattern in French context
        marc_info, copyright_info = detector.detect(
            "Index to French Literature",  # English pattern
            "French Literature",
            "fre",  # French language specified
        )

        # Should detect English pattern with slight penalty
        assert marc_info.is_derived is True
        assert marc_info.pattern_matched == "index_eng"  # Suffix indicates cross-language
        assert marc_info.confidence == 0.95 * 0.9  # Cross-language penalty applied

    def test_both_derived_same_type(self, detector: DerivedWorkDetector):
        """Test when both titles are the same type of derived work"""
        marc_info, copyright_info = detector.detect(
            "Index to American Poetry", "Index of American Poetry", "eng"
        )

        assert marc_info.is_derived is True
        assert copyright_info.is_derived is True
        assert marc_info.pattern_matched == "index"
        assert copyright_info.pattern_matched == "index"

    def test_both_derived_different_types(self, detector: DerivedWorkDetector):
        """Test when both titles are different types of derived works"""
        marc_info, copyright_info = detector.detect(
            "Index to World Literature", "Bibliography of World Literature", "eng"
        )

        assert marc_info.is_derived is True
        assert copyright_info.is_derived is True
        assert marc_info.pattern_matched == "index"
        assert copyright_info.pattern_matched == "bibliography"

    def test_penalty_calculation_none_derived(self, detector: DerivedWorkDetector):
        """Test penalty calculation when neither is derived"""
        marc_info = DerivedWorkInfo(is_derived=False)
        copyright_info = DerivedWorkInfo(is_derived=False)

        should_penalize, adjusted_score = detector.should_penalize_match(
            marc_info, copyright_info, 80.0
        )

        assert should_penalize is False
        assert adjusted_score == 80.0

    def test_penalty_calculation_both_same_type(self, detector: DerivedWorkDetector):
        """Test penalty when both are same type of derived work"""
        marc_info = DerivedWorkInfo(is_derived=True, pattern_matched="index", confidence=0.95)
        copyright_info = DerivedWorkInfo(is_derived=True, pattern_matched="index", confidence=0.95)

        should_penalize, adjusted_score = detector.should_penalize_match(
            marc_info, copyright_info, 80.0
        )

        assert should_penalize is True
        # Small penalty (max 10%) for same type
        expected = 80.0 * (1.0 - (0.95 * 0.1))
        assert abs(adjusted_score - expected) < 0.01

    def test_penalty_calculation_both_different_types(self, detector: DerivedWorkDetector):
        """Test penalty when both are different types of derived works"""
        marc_info = DerivedWorkInfo(is_derived=True, pattern_matched="index", confidence=0.95)
        copyright_info = DerivedWorkInfo(
            is_derived=True, pattern_matched="bibliography", confidence=0.9
        )

        should_penalize, adjusted_score = detector.should_penalize_match(
            marc_info, copyright_info, 80.0
        )

        assert should_penalize is True
        # Moderate penalty (max 30%) for different types
        avg_conf = (0.95 + 0.9) / 2
        expected = 80.0 * (1.0 - (avg_conf * 0.3))
        assert abs(adjusted_score - expected) < 0.01

    def test_penalty_calculation_one_derived(self, detector: DerivedWorkDetector):
        """Test penalty when only one is a derived work"""
        marc_info = DerivedWorkInfo(is_derived=True, pattern_matched="index", confidence=0.95)
        copyright_info = DerivedWorkInfo(is_derived=False)

        should_penalize, adjusted_score = detector.should_penalize_match(
            marc_info, copyright_info, 80.0
        )

        assert should_penalize is True
        # Strong penalty (max 50%) when only one is derived
        expected = 80.0 * (1.0 - (0.95 * 0.5))
        assert abs(adjusted_score - expected) < 0.01

    def test_integration_with_score_combiner(self, score_combiner: ScoreCombiner):
        """Test integration of derived work detection with score combiner"""
        # Case 1: One is derived work (index)
        marc_derived = DerivedWorkInfo(is_derived=True, pattern_matched="index", confidence=0.95)
        copyright_derived = DerivedWorkInfo(is_derived=False)

        # Good field scores but one is derived work
        combined = score_combiner.combine_scores(
            title_score=75.0,
            author_score=65.0,
            publisher_score=70.0,
            has_generic_title=False,
            use_config_weights=True,
            has_lccn_match=False,
            marc_derived=marc_derived,
            copyright_derived=copyright_derived,
        )

        # Should be penalized (30% max penalty from 0.95 confidence in refined version)
        # Base score would be around 70, with 30% penalty should be around 49-51
        assert combined < 55, f"Derived work should be penalized, got {combined}"
        assert combined > 45, f"Penalty shouldn't be too severe, got {combined}"

    def test_real_example_index_colophon(self, detector: DerivedWorkDetector):
        """Test real example: 'Index, the Colophon' case"""
        marc_info, copyright_info = detector.detect("Index, the Colophon", "The Colophon", "eng")

        # MARC title starts with "Index" which should be detected
        assert marc_info.is_derived is False  # "Index," alone isn't a pattern
        assert copyright_info.is_derived is False

        # But with proper pattern
        marc_info2, copyright_info2 = detector.detect(
            "Index to the Colophon", "The Colophon", "eng"
        )
        assert marc_info2.is_derived is True
        assert marc_info2.pattern_matched == "index"
