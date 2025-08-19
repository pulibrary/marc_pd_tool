# tests/unit/application/processing/matching/test_score_combiner.py

"""Comprehensive tests for the ScoreCombiner class to achieve 100% coverage"""

# Standard library imports
from unittest.mock import Mock

# Third party imports
from pytest import fixture

# Local imports
from marc_pd_tool.application.processing.matching._score_combiner import ScoreCombiner
from marc_pd_tool.infrastructure.config import ConfigLoader


class TestScoreCombiner:
    """Test the ScoreCombiner class"""

    @fixture
    def mock_config(self):
        """Create a mock configuration loader"""
        config = Mock(spec=ConfigLoader)
        config.config = {
            "matching": {
                "adaptive_weighting": {
                    "title_weight": 0.5,
                    "author_weight": 0.3,
                    "publisher_weight": 0.2,
                    "generic_title_penalty": 0.8,
                }
            }
        }
        return config

    @fixture
    def mock_config_with_scenarios(self):
        """Create a mock configuration with scoring weight scenarios"""
        config = Mock(spec=ConfigLoader)
        config.config = {
            "matching": {
                "adaptive_weighting": {
                    "title_weight": 0.5,
                    "author_weight": 0.3,
                    "publisher_weight": 0.2,
                    "generic_title_penalty": 0.8,
                }
            }
        }

        # Mock get_scoring_weights to return different weights for different scenarios
        def mock_get_scoring_weights(scenario):
            scenarios = {
                "normal_with_publisher": {"title": 0.6, "author": 0.25, "publisher": 0.15},
                "generic_with_publisher": {"title": 0.3, "author": 0.45, "publisher": 0.25},
                "normal_no_publisher": {"title": 0.7, "author": 0.3},
                "generic_no_publisher": {"title": 0.4, "author": 0.6},
            }
            return scenarios.get(scenario)

        config.get_scoring_weights = Mock(side_effect=mock_get_scoring_weights)
        return config

    @fixture
    def mock_config_no_scenarios(self):
        """Create a mock configuration that returns None for scoring weights"""
        config = Mock(spec=ConfigLoader)
        config.config = {
            "matching": {
                "adaptive_weighting": {
                    "title_weight": 0.5,
                    "author_weight": 0.3,
                    "publisher_weight": 0.2,
                    "generic_title_penalty": 0.8,
                }
            }
        }
        config.get_scoring_weights = Mock(return_value=None)
        return config

    @fixture
    def mock_config_missing_weights(self):
        """Create a mock configuration with missing weight values"""
        config = Mock(spec=ConfigLoader)
        config.config = {"matching": {"adaptive_weighting": {}}}  # No weights defined
        return config

    @fixture
    def mock_config_partial_weights(self):
        """Create a mock configuration with partial weight values"""
        config = Mock(spec=ConfigLoader)
        config.config = {
            "matching": {
                "adaptive_weighting": {
                    "title_weight": 0.6,
                    # Missing author_weight, publisher_weight, generic_title_penalty
                }
            }
        }
        return config

    def test_initialization_with_all_weights(self, mock_config):
        """Test initialization with all weights present in config"""
        combiner = ScoreCombiner(mock_config)

        assert combiner.default_title_weight == 0.5
        assert combiner.default_author_weight == 0.3
        assert combiner.default_publisher_weight == 0.2
        assert combiner.generic_title_penalty == 0.8

    def test_initialization_with_missing_weights(self, mock_config_missing_weights):
        """Test initialization with missing weights uses defaults"""
        combiner = ScoreCombiner(mock_config_missing_weights)

        # Should use hardcoded defaults when not in config
        assert combiner.default_title_weight == 0.5
        assert combiner.default_author_weight == 0.3
        assert combiner.default_publisher_weight == 0.2
        assert combiner.generic_title_penalty == 0.8

    def test_initialization_with_partial_weights(self, mock_config_partial_weights):
        """Test initialization with partial weights uses mix of config and defaults"""
        combiner = ScoreCombiner(mock_config_partial_weights)

        # Should use config value for title_weight
        assert combiner.default_title_weight == 0.6
        # Should use defaults for missing values
        assert combiner.default_author_weight == 0.3
        assert combiner.default_publisher_weight == 0.2
        assert combiner.generic_title_penalty == 0.8

    def test_get_weight_with_nested_missing_keys(self):
        """Test _get_weight handles missing nested keys gracefully"""
        config = Mock(spec=ConfigLoader)
        config.config = {}  # Empty config

        combiner = ScoreCombiner(config)
        # Should use all defaults
        assert combiner.default_title_weight == 0.5

    def test_combine_scores_normal_with_publisher(self, mock_config_with_scenarios):
        """Test score combination for normal title with publisher"""
        combiner = ScoreCombiner(mock_config_with_scenarios)

        score = combiner.combine_scores(
            title_score=80.0,
            author_score=70.0,
            publisher_score=60.0,
            has_generic_title=False,
            use_config_weights=True,
        )

        # Expected: 80*0.6 + 70*0.25 + 60*0.15 = 48 + 17.5 + 9 = 74.5
        assert score == 74.5

    def test_combine_scores_generic_with_publisher(self, mock_config_with_scenarios):
        """Test score combination for generic title with publisher"""
        combiner = ScoreCombiner(mock_config_with_scenarios)

        score = combiner.combine_scores(
            title_score=80.0,
            author_score=70.0,
            publisher_score=60.0,
            has_generic_title=True,
            use_config_weights=True,
        )

        # Weights from config: title=0.3, author=0.45, publisher=0.25
        # With generic penalty: title_weight = 0.3 * 0.8 = 0.24
        # Normalized: total = 0.24 + 0.45 + 0.25 = 0.94
        # title: 0.24/0.94 = 0.2553, author: 0.45/0.94 = 0.4787, publisher: 0.25/0.94 = 0.2660
        # Score: 80*0.2553 + 70*0.4787 + 60*0.2660 ≈ 69.89
        assert 69.5 < score < 70.5  # Allow for rounding

    def test_combine_scores_normal_no_publisher(self, mock_config_with_scenarios):
        """Test score combination for normal title without publisher"""
        combiner = ScoreCombiner(mock_config_with_scenarios)

        score = combiner.combine_scores(
            title_score=80.0,
            author_score=70.0,
            publisher_score=0.0,
            has_generic_title=False,
            use_config_weights=True,
        )

        # Weights from config: title=0.7, author=0.3, publisher missing (defaults to 0.2)
        # Total weight = 0.7 + 0.3 + 0.2 = 1.2
        # Normalized: title=0.7/1.2=0.583, author=0.3/1.2=0.25, publisher=0.2/1.2=0.167
        # Score = 80*0.583 + 70*0.25 + 0*0.167 = 46.67 + 17.5 = 64.17
        assert score == 64.17

    def test_combine_scores_generic_no_publisher(self, mock_config_with_scenarios):
        """Test score combination for generic title without publisher"""
        combiner = ScoreCombiner(mock_config_with_scenarios)

        score = combiner.combine_scores(
            title_score=80.0,
            author_score=70.0,
            publisher_score=0.0,
            has_generic_title=True,
            use_config_weights=True,
        )

        # Weights from config: title=0.4, author=0.6, publisher missing (defaults to 0.2)
        # With generic penalty: title_weight = 0.4 * 0.8 = 0.32
        # Total = 0.32 + 0.6 + 0.2 = 1.12
        # Normalized: title=0.32/1.12=0.286, author=0.6/1.12=0.536, publisher=0.2/1.12=0.179
        # Score: 80*0.286 + 70*0.536 + 0*0.179 = 22.86 + 37.50 = 60.36
        assert score == 60.36

    def test_combine_scores_fallback_to_defaults(self, mock_config_no_scenarios):
        """Test score combination falls back to defaults when no scenario weights"""
        combiner = ScoreCombiner(mock_config_no_scenarios)

        # Test with publisher
        score = combiner.combine_scores(
            title_score=80.0,
            author_score=70.0,
            publisher_score=60.0,
            has_generic_title=False,
            use_config_weights=True,
        )

        # Should use defaults: title=0.5, author=0.3, publisher=0.2
        # Expected: 80*0.5 + 70*0.3 + 60*0.2 = 40 + 21 + 12 = 73.0
        assert score == 73.0

    def test_combine_scores_fallback_no_publisher(self, mock_config_no_scenarios):
        """Test fallback to defaults without publisher score"""
        combiner = ScoreCombiner(mock_config_no_scenarios)

        score = combiner.combine_scores(
            title_score=80.0,
            author_score=70.0,
            publisher_score=0.0,
            has_generic_title=False,
            use_config_weights=True,
        )

        # Should use defaults: title=0.5, author=0.3, publisher=0 (no publisher)
        # Normalized: total = 0.5 + 0.3 = 0.8
        # title: 0.5/0.8 = 0.625, author: 0.3/0.8 = 0.375
        # Score: 80*0.625 + 70*0.375 = 50 + 26.25 = 76.25
        assert score == 76.25

    def test_combine_scores_dynamic_weights_high_title(self, mock_config):
        """Test dynamic weight calculation with high title score"""
        combiner = ScoreCombiner(mock_config)

        score = combiner.combine_scores(
            title_score=95.0,  # >= 90
            author_score=70.0,
            publisher_score=60.0,
            has_generic_title=False,
            use_config_weights=False,  # Use dynamic weights
        )

        # Dynamic weights: title=0.6, author=0.25, publisher=0.15
        # Expected: 95*0.6 + 70*0.25 + 60*0.15 = 57 + 17.5 + 9 = 83.5
        assert score == 83.5

    def test_combine_scores_dynamic_weights_high_title_generic(self, mock_config):
        """Test dynamic weights with high title score but generic title"""
        combiner = ScoreCombiner(mock_config)

        score = combiner.combine_scores(
            title_score=95.0,  # >= 90
            author_score=70.0,
            publisher_score=60.0,
            has_generic_title=True,  # Generic title
            use_config_weights=False,  # Use dynamic weights
        )

        # High title score but generic, so doesn't get boosted weight
        # Falls through to default weights: title=0.5, author=0.3, publisher=0.2
        # With generic penalty: title_weight = 0.5 * 0.8 = 0.4
        # Normalized: total = 0.4 + 0.3 + 0.2 = 0.9
        # title: 0.4/0.9 = 0.4444, author: 0.3/0.9 = 0.3333, publisher: 0.2/0.9 = 0.2222
        # Score: 95*0.4444 + 70*0.3333 + 60*0.2222 ≈ 78.89
        assert 78.5 < score < 79.5

    def test_combine_scores_dynamic_weights_high_author(self, mock_config):
        """Test dynamic weight calculation with high author score"""
        combiner = ScoreCombiner(mock_config)

        score = combiner.combine_scores(
            title_score=70.0,
            author_score=92.0,  # >= 90
            publisher_score=60.0,
            has_generic_title=False,
            use_config_weights=False,  # Use dynamic weights
        )

        # Dynamic weights: title=0.4, author=0.5, publisher=0.2
        # Normalized: total = 0.4 + 0.5 + 0.2 = 1.1
        # title: 0.4/1.1 = 0.3636, author: 0.5/1.1 = 0.4545, publisher: 0.2/1.1 = 0.1818
        # Score: 70*0.3636 + 92*0.4545 + 60*0.1818 ≈ 78.18
        assert 78.0 < score < 78.5

    def test_combine_scores_dynamic_weights_high_author_generic(self, mock_config):
        """Test dynamic weights with high author score and generic title"""
        combiner = ScoreCombiner(mock_config)

        score = combiner.combine_scores(
            title_score=70.0,
            author_score=92.0,  # >= 90
            publisher_score=60.0,
            has_generic_title=True,  # Generic title
            use_config_weights=False,  # Use dynamic weights
        )

        # Dynamic weights: title=0.3 (generic), author=0.5, publisher=0.2
        # With generic penalty: title_weight = 0.3 * 0.8 = 0.24
        # Normalized: total = 0.24 + 0.5 + 0.2 = 0.94
        # title: 0.24/0.94 = 0.2553, author: 0.5/0.94 = 0.5319, publisher: 0.2/0.94 = 0.2128
        # Score: 70*0.2553 + 92*0.5319 + 60*0.2128 ≈ 79.63
        assert 79.0 < score < 80.0

    def test_combine_scores_dynamic_weights_high_author_no_publisher(self, mock_config):
        """Test dynamic weights with high author score and no publisher"""
        combiner = ScoreCombiner(mock_config)

        score = combiner.combine_scores(
            title_score=70.0,
            author_score=92.0,  # >= 90
            publisher_score=0.0,  # No publisher
            has_generic_title=False,
            use_config_weights=False,  # Use dynamic weights
        )

        # Dynamic weights: title=0.4, author=0.5, publisher=0.1
        # Total = 0.4 + 0.5 + 0.1 = 1.0
        # Score: 70*0.4 + 92*0.5 + 0*0.1 = 28 + 46 + 0 = 74.0
        assert score == 74.0

    def test_combine_scores_dynamic_weights_high_publisher(self, mock_config):
        """Test dynamic weight calculation with high publisher score"""
        combiner = ScoreCombiner(mock_config)

        score = combiner.combine_scores(
            title_score=70.0,
            author_score=60.0,
            publisher_score=85.0,  # >= 80
            has_generic_title=False,
            use_config_weights=False,  # Use dynamic weights
        )

        # Dynamic weights: title=0.35, author=0.35, publisher=0.3
        # Expected: 70*0.35 + 60*0.35 + 85*0.3 = 24.5 + 21 + 25.5 = 71.0
        assert score == 71.0

    def test_combine_scores_dynamic_weights_high_publisher_generic(self, mock_config):
        """Test dynamic weights with high publisher score and generic title"""
        combiner = ScoreCombiner(mock_config)

        score = combiner.combine_scores(
            title_score=70.0,
            author_score=60.0,
            publisher_score=85.0,  # >= 80
            has_generic_title=True,  # Generic title
            use_config_weights=False,  # Use dynamic weights
        )

        # Dynamic weights: title=0.25 (generic), author=0.35, publisher=0.3
        # With generic penalty: title_weight = 0.25 * 0.8 = 0.2
        # Normalized: total = 0.2 + 0.35 + 0.3 = 0.85
        # title: 0.2/0.85 = 0.2353, author: 0.35/0.85 = 0.4118, publisher: 0.3/0.85 = 0.3529
        # Score: 70*0.2353 + 60*0.4118 + 85*0.3529 ≈ 71.18
        assert 71.0 < score < 71.5

    def test_combine_scores_dynamic_weights_default_fallback(self, mock_config):
        """Test dynamic weights fall back to defaults for moderate scores"""
        combiner = ScoreCombiner(mock_config)

        score = combiner.combine_scores(
            title_score=70.0,  # < 90
            author_score=60.0,  # < 90
            publisher_score=50.0,  # < 80
            has_generic_title=False,
            use_config_weights=False,  # Use dynamic weights
        )

        # Falls back to default weights: title=0.5, author=0.3, publisher=0.2
        # Expected: 70*0.5 + 60*0.3 + 50*0.2 = 35 + 18 + 10 = 63.0
        assert score == 63.0

    def test_combine_scores_dynamic_weights_no_publisher_fallback(self, mock_config):
        """Test dynamic weights fallback with no publisher score"""
        combiner = ScoreCombiner(mock_config)

        score = combiner.combine_scores(
            title_score=70.0,
            author_score=60.0,
            publisher_score=0.0,  # No publisher
            has_generic_title=False,
            use_config_weights=False,  # Use dynamic weights
        )

        # Falls back to defaults: title=0.5, author=0.3, publisher=0 (no publisher)
        # Normalized: total = 0.5 + 0.3 = 0.8
        # title: 0.5/0.8 = 0.625, author: 0.3/0.8 = 0.375
        # Score: 70*0.625 + 60*0.375 = 43.75 + 22.5 = 66.25
        assert score == 66.25

    def test_combine_scores_all_zero_scores(self, mock_config_no_scenarios):
        """Test combination with all zero scores"""
        combiner = ScoreCombiner(mock_config_no_scenarios)

        score = combiner.combine_scores(
            title_score=0.0,
            author_score=0.0,
            publisher_score=0.0,
            has_generic_title=False,
            use_config_weights=True,
        )

        assert score == 0.0

    def test_combine_scores_zero_total_weight(self, mock_config):
        """Test edge case where total weight could be zero"""
        # This is a theoretical edge case - in practice weights should never all be zero
        combiner = ScoreCombiner(mock_config)

        # Manually set all weights to zero to test the edge case
        combiner.default_title_weight = 0.0
        combiner.default_author_weight = 0.0
        combiner.default_publisher_weight = 0.0

        score = combiner.combine_scores(
            title_score=80.0,
            author_score=70.0,
            publisher_score=0.0,  # No publisher score
            has_generic_title=False,
            use_config_weights=False,  # Use dynamic weights
        )

        # When total_weight is 0, normalization is skipped, so score would be 0
        assert score == 0.0

    def test_combine_scores_perfect_scores(self, mock_config_with_scenarios):
        """Test combination with perfect scores"""
        combiner = ScoreCombiner(mock_config_with_scenarios)

        score = combiner.combine_scores(
            title_score=100.0,
            author_score=100.0,
            publisher_score=100.0,
            has_generic_title=False,
            use_config_weights=True,
        )

        # All scores are 100, so result should be 100 regardless of weights
        assert score == 100.0

    def test_combine_scores_rounding(self, mock_config_no_scenarios):
        """Test that scores are properly rounded to 2 decimal places"""
        combiner = ScoreCombiner(mock_config_no_scenarios)

        score = combiner.combine_scores(
            title_score=33.333,
            author_score=66.666,
            publisher_score=99.999,
            has_generic_title=False,
            use_config_weights=True,
        )

        # Result should be rounded to 2 decimal places
        assert isinstance(score, float)
        assert score == round(score, 2)

    def test_calculate_dynamic_weights_all_branches(self, mock_config):
        """Test all branches of _calculate_dynamic_weights method"""
        combiner = ScoreCombiner(mock_config)

        # Test high title score (non-generic)
        weights = combiner._calculate_dynamic_weights(
            title_score=95.0, author_score=50.0, publisher_score=50.0, has_generic_title=False
        )
        assert weights == (0.6, 0.25, 0.15)

        # Test high author score
        weights = combiner._calculate_dynamic_weights(
            title_score=50.0, author_score=95.0, publisher_score=50.0, has_generic_title=False
        )
        assert weights == (0.4, 0.5, 0.2)

        # Test high author score with generic title
        weights = combiner._calculate_dynamic_weights(
            title_score=50.0, author_score=95.0, publisher_score=50.0, has_generic_title=True
        )
        assert weights == (0.3, 0.5, 0.2)

        # Test high author score with no publisher
        weights = combiner._calculate_dynamic_weights(
            title_score=50.0, author_score=95.0, publisher_score=0.0, has_generic_title=False
        )
        assert weights == (0.4, 0.5, 0.1)

        # Test high publisher score
        weights = combiner._calculate_dynamic_weights(
            title_score=50.0, author_score=50.0, publisher_score=85.0, has_generic_title=False
        )
        assert weights == (0.35, 0.35, 0.3)

        # Test high publisher score with generic title
        weights = combiner._calculate_dynamic_weights(
            title_score=50.0, author_score=50.0, publisher_score=85.0, has_generic_title=True
        )
        assert weights == (0.25, 0.35, 0.3)

        # Test default case
        weights = combiner._calculate_dynamic_weights(
            title_score=50.0, author_score=50.0, publisher_score=50.0, has_generic_title=False
        )
        assert weights == (0.5, 0.3, 0.2)

        # Test default case with no publisher
        weights = combiner._calculate_dynamic_weights(
            title_score=50.0, author_score=50.0, publisher_score=0.0, has_generic_title=False
        )
        assert weights == (0.5, 0.3, 0)

    def test_get_weight_type_conversion(self):
        """Test that _get_weight properly converts values to float"""
        config = Mock(spec=ConfigLoader)
        config.config = {
            "matching": {
                "adaptive_weighting": {
                    "title_weight": "0.5",  # String that should be converted
                    "author_weight": 0.3,  # Already a float
                    "publisher_weight": 1,  # Integer that should be converted
                }
            }
        }

        combiner = ScoreCombiner(config)

        # All values should be converted to float
        assert combiner.default_title_weight == 0.5
        assert isinstance(combiner.default_title_weight, float)
        assert combiner.default_author_weight == 0.3
        assert isinstance(combiner.default_author_weight, float)
        assert combiner.default_publisher_weight == 1.0
        assert isinstance(combiner.default_publisher_weight, float)
