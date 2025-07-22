"""Test the matching API abstract base classes and contracts"""

# Standard library imports
from abc import ABC

# Third party imports
import pytest

# Local imports
from marc_pd_tool.data.publication import Publication
from marc_pd_tool.processing.matching_api import MatchingEngine
from marc_pd_tool.processing.matching_api import ScoreCombiner
from marc_pd_tool.processing.matching_api import SimilarityCalculator
from marc_pd_tool.processing.matching_api import SimilarityScores


class TestSimilarityScores:
    """Test the SimilarityScores dataclass"""

    def test_similarity_scores_creation(self):
        """Test creating SimilarityScores with all fields"""
        scores = SimilarityScores(title=85.5, author=72.3, publisher=90.1, combined=82.7)

        assert scores.title == 85.5
        assert scores.author == 72.3
        assert scores.publisher == 90.1
        assert scores.combined == 82.7

    def test_similarity_scores_dataclass_features(self):
        """Test that SimilarityScores works as a proper dataclass"""
        scores1 = SimilarityScores(85.5, 72.3, 90.1, 82.7)
        scores2 = SimilarityScores(85.5, 72.3, 90.1, 82.7)
        scores3 = SimilarityScores(80.0, 70.0, 85.0, 78.0)

        # Test equality
        assert scores1 == scores2
        assert scores1 != scores3

        # Test string representation
        assert "title=85.5" in str(scores1)
        assert "author=72.3" in str(scores1)


class TestAbstractBaseClasses:
    """Test that abstract base classes cannot be instantiated and enforce contracts"""

    def test_similarity_calculator_is_abstract(self):
        """Test that SimilarityCalculator cannot be instantiated directly"""
        with pytest.raises(TypeError):
            SimilarityCalculator()

    def test_score_combiner_is_abstract(self):
        """Test that ScoreCombiner cannot be instantiated directly"""
        with pytest.raises(TypeError):
            ScoreCombiner()

    def test_matching_engine_is_abstract(self):
        """Test that MatchingEngine cannot be instantiated directly"""
        with pytest.raises(TypeError):
            MatchingEngine()

    def test_similarity_calculator_inheritance(self):
        """Test that SimilarityCalculator requires all abstract methods to be implemented"""

        # Incomplete implementation should fail
        class IncompleteSimilarityCalculator(SimilarityCalculator):
            def calculate_title_similarity(self, marc_title: str, copyright_title: str) -> float:
                return 85.0

            # Missing calculate_author_similarity and calculate_publisher_similarity

        with pytest.raises(TypeError):
            IncompleteSimilarityCalculator()

        # Complete implementation should work
        class CompleteSimilarityCalculator(SimilarityCalculator):
            def calculate_title_similarity(self, marc_title: str, copyright_title: str) -> float:
                return 85.0

            def calculate_author_similarity(self, marc_author: str, copyright_author: str) -> float:
                return 75.0

            def calculate_publisher_similarity(
                self, marc_publisher: str, copyright_publisher: str, copyright_full_text: str = ""
            ) -> float:
                return 90.0

        # Should not raise an error
        calculator = CompleteSimilarityCalculator()
        assert calculator.calculate_title_similarity("test", "test") == 85.0

    def test_score_combiner_inheritance(self):
        """Test that ScoreCombiner requires combine_scores method to be implemented"""

        # Incomplete implementation should fail
        class IncompleteScoreCombiner(ScoreCombiner):
            pass

        with pytest.raises(TypeError):
            IncompleteScoreCombiner()

        # Complete implementation should work
        class CompleteScoreCombiner(ScoreCombiner):
            def combine_scores(
                self,
                title_score,
                author_score,
                publisher_score,
                marc_pub,
                copyright_pub,
                generic_detector=None,
            ):
                return (title_score + author_score + publisher_score) / 3

        # Should not raise an error
        combiner = CompleteScoreCombiner()
        pub = Publication("Test Title")
        assert combiner.combine_scores(80, 70, 90, pub, pub) == 80.0

    def test_matching_engine_inheritance(self):
        """Test that MatchingEngine requires find_best_match method to be implemented"""

        # Incomplete implementation should fail
        class IncompleteMatchingEngine(MatchingEngine):
            pass

        with pytest.raises(TypeError):
            IncompleteMatchingEngine()

        # Complete implementation should work
        class CompleteMatchingEngine(MatchingEngine):
            def find_best_match(
                self,
                marc_pub,
                copyright_pubs,
                title_threshold,
                author_threshold,
                year_tolerance,
                publisher_threshold,
                early_exit_title,
                early_exit_author,
                generic_detector=None,
            ):
                return None

        # Should not raise an error
        engine = CompleteMatchingEngine()
        pub = Publication("Test Title")
        result = engine.find_best_match(pub, [pub], 80, 70, 2, 60, 95, 90)
        assert result is None


class TestAPIContracts:
    """Test the expected behavior and contracts of the API"""

    def test_similarity_calculator_contract(self):
        """Test that SimilarityCalculator methods have expected signatures and behavior"""

        class TestSimilarityCalculator(SimilarityCalculator):
            def calculate_title_similarity(self, marc_title: str, copyright_title: str) -> float:
                # Simple exact match test
                return 100.0 if marc_title == copyright_title else 50.0

            def calculate_author_similarity(self, marc_author: str, copyright_author: str) -> float:
                # Simple exact match test
                return 100.0 if marc_author == copyright_author else 25.0

            def calculate_publisher_similarity(
                self, marc_publisher: str, copyright_publisher: str, copyright_full_text: str = ""
            ) -> float:
                # Use full_text if available, otherwise direct comparison
                if copyright_full_text:
                    return 75.0 if marc_publisher in copyright_full_text else 25.0
                return 100.0 if marc_publisher == copyright_publisher else 0.0

        calculator = TestSimilarityCalculator()

        # Test title similarity
        assert calculator.calculate_title_similarity("Same Title", "Same Title") == 100.0
        assert calculator.calculate_title_similarity("Different", "Title") == 50.0

        # Test author similarity
        assert calculator.calculate_author_similarity("Smith, John", "Smith, John") == 100.0
        assert calculator.calculate_author_similarity("Smith, John", "Doe, Jane") == 25.0

        # Test publisher similarity with direct comparison
        assert calculator.calculate_publisher_similarity("Penguin", "Penguin", "") == 100.0
        assert calculator.calculate_publisher_similarity("Penguin", "Random House", "") == 0.0

        # Test publisher similarity with full text
        assert (
            calculator.calculate_publisher_similarity("Penguin", "", "Published by Penguin Books")
            == 75.0
        )
        assert (
            calculator.calculate_publisher_similarity("Penguin", "", "Published by Random House")
            == 25.0
        )

    def test_score_combiner_contract(self):
        """Test that ScoreCombiner methods have expected signatures and behavior"""

        class TestScoreCombiner(ScoreCombiner):
            def combine_scores(
                self,
                title_score,
                author_score,
                publisher_score,
                marc_pub,
                copyright_pub,
                generic_detector=None,
            ):
                # Simple weighted average
                return (title_score * 0.6) + (author_score * 0.3) + (publisher_score * 0.1)

        combiner = TestScoreCombiner()
        pub = Publication("Test Title")

        # Test score combination
        combined = combiner.combine_scores(80, 70, 90, pub, pub)
        expected = (80 * 0.6) + (70 * 0.3) + (90 * 0.1)  # 48 + 21 + 9 = 78
        assert combined == expected

    def test_matching_engine_contract(self):
        """Test that MatchingEngine methods have expected signatures and behavior"""

        class TestMatchingEngine(MatchingEngine):
            def find_best_match(
                self,
                marc_pub,
                copyright_pubs,
                title_threshold,
                author_threshold,
                year_tolerance,
                publisher_threshold,
                early_exit_title,
                early_exit_author,
                generic_detector=None,
            ):
                # Simple implementation that returns first match above threshold
                for pub in copyright_pubs:
                    if marc_pub.title == pub.title:
                        return {
                            "marc_record": marc_pub.to_dict(),
                            "copyright_record": pub.to_dict(),
                            "similarity_scores": {
                                "title": 100.0,
                                "author": 100.0,
                                "publisher": 100.0,
                                "combined": 100.0,
                            },
                        }
                return None

        engine = TestMatchingEngine()

        # Test with matching publications
        marc_pub = Publication("Test Title", "Test Author")
        copyright_pub = Publication("Test Title", "Test Author")
        other_pub = Publication("Other Title", "Other Author")

        result = engine.find_best_match(marc_pub, [other_pub, copyright_pub], 80, 70, 2, 60, 95, 90)
        assert result is not None
        assert result["similarity_scores"]["combined"] == 100.0

        # Test with no matching publications
        result = engine.find_best_match(marc_pub, [other_pub], 80, 70, 2, 60, 95, 90)
        assert result is None


class TestAPIIntegration:
    """Test that the API components work together correctly"""

    def test_components_can_be_composed(self):
        """Test that different components can be mixed and matched"""

        class SimpleSimilarityCalculator(SimilarityCalculator):
            def calculate_title_similarity(self, marc_title: str, copyright_title: str) -> float:
                return 80.0

            def calculate_author_similarity(self, marc_author: str, copyright_author: str) -> float:
                return 70.0

            def calculate_publisher_similarity(
                self, marc_publisher: str, copyright_publisher: str, copyright_full_text: str = ""
            ) -> float:
                return 60.0

        class SimpleScoreCombiner(ScoreCombiner):
            def combine_scores(
                self,
                title_score,
                author_score,
                publisher_score,
                marc_pub,
                copyright_pub,
                generic_detector=None,
            ):
                return (title_score + author_score + publisher_score) / 3

        class ComposedMatchingEngine(MatchingEngine):
            def __init__(self, similarity_calculator, score_combiner):
                self.similarity_calculator = similarity_calculator
                self.score_combiner = score_combiner

            def find_best_match(
                self,
                marc_pub,
                copyright_pubs,
                title_threshold,
                author_threshold,
                year_tolerance,
                publisher_threshold,
                early_exit_title,
                early_exit_author,
                generic_detector=None,
            ):
                if not copyright_pubs:
                    return None

                best_pub = copyright_pubs[0]
                title_score = self.similarity_calculator.calculate_title_similarity("", "")
                author_score = self.similarity_calculator.calculate_author_similarity("", "")
                publisher_score = self.similarity_calculator.calculate_publisher_similarity("", "")
                combined_score = self.score_combiner.combine_scores(
                    title_score, author_score, publisher_score, marc_pub, best_pub
                )

                return {
                    "marc_record": marc_pub.to_dict(),
                    "copyright_record": best_pub.to_dict(),
                    "similarity_scores": {
                        "title": title_score,
                        "author": author_score,
                        "publisher": publisher_score,
                        "combined": combined_score,
                    },
                }

        # Test composition
        calculator = SimpleSimilarityCalculator()
        combiner = SimpleScoreCombiner()
        engine = ComposedMatchingEngine(calculator, combiner)

        marc_pub = Publication("Test Title")
        copyright_pub = Publication("Test Title")

        result = engine.find_best_match(marc_pub, [copyright_pub], 80, 70, 2, 60, 95, 90)
        assert result is not None
        assert result["similarity_scores"]["title"] == 80.0
        assert result["similarity_scores"]["author"] == 70.0
        assert result["similarity_scores"]["publisher"] == 60.0
        assert result["similarity_scores"]["combined"] == 70.0  # (80+70+60)/3
