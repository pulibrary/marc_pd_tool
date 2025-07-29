# tests/test_analysis/test_score_analyzer.py

"""Test similarity score analysis for ground truth pairs"""

# Standard library imports
from unittest.mock import MagicMock
from unittest.mock import patch

# Third party imports
from pytest import approx

# Local imports
from marc_pd_tool.data.ground_truth import GroundTruthAnalysis
from marc_pd_tool.data.ground_truth import GroundTruthPair
from marc_pd_tool.data.ground_truth import ScoreDistribution
from marc_pd_tool.data.publication import Publication
from marc_pd_tool.processing.matching_engine import DataMatcher
from marc_pd_tool.processing.score_analyzer import ScoreAnalyzer


class TestScoreDistribution:
    """Test the ScoreDistribution dataclass"""

    def test_empty_distribution(self):
        """Test distribution with no scores"""
        dist = ScoreDistribution("test", [])

        assert dist.mean_score == 0.0
        assert dist.median_score == 0.0
        assert dist.std_dev == 0.0
        assert dist.min_score == 0.0
        assert dist.max_score == 0.0
        assert dist.percentile_5 == 0.0
        assert dist.percentile_25 == 0.0
        assert dist.percentile_75 == 0.0
        assert dist.percentile_95 == 0.0

    def test_single_score_distribution(self):
        """Test distribution with single score"""
        dist = ScoreDistribution("test", [85.0])

        assert dist.mean_score == 85.0
        assert dist.median_score == 85.0
        assert dist.std_dev == 0.0
        assert dist.min_score == 85.0
        assert dist.max_score == 85.0
        assert dist.percentile_5 == 85.0
        assert dist.percentile_25 == 85.0
        assert dist.percentile_75 == 85.0
        assert dist.percentile_95 == 85.0

    def test_multiple_scores_distribution(self):
        """Test distribution with multiple scores"""
        scores = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
        dist = ScoreDistribution("test", scores)

        assert dist.mean_score == 55.0
        assert dist.median_score == 55.0
        assert dist.std_dev == approx(30.28, abs=0.1)
        assert dist.min_score == 10.0
        assert dist.max_score == 100.0

        # Test percentiles
        assert dist.percentile_5 == approx(14.5, abs=0.1)
        assert dist.percentile_25 == approx(32.5, abs=0.1)
        assert dist.percentile_75 == approx(77.5, abs=0.1)
        assert dist.percentile_95 == approx(95.5, abs=0.1)


class TestScoreAnalyzer:
    """Test the ScoreAnalyzer class"""

    def test_initialization_default_matcher(self):
        """Test analyzer initialization with default matcher"""
        analyzer = ScoreAnalyzer()

        assert analyzer.matcher is not None
        assert isinstance(analyzer.matcher, DataMatcher)
        assert analyzer.generic_detector is not None

    def test_initialization_custom_matcher(self):
        """Test analyzer initialization with custom matcher"""
        custom_matcher = MagicMock()
        analyzer = ScoreAnalyzer(matcher=custom_matcher)

        assert analyzer.matcher is custom_matcher

    def test_analyze_ground_truth_scores_basic(self):
        """Test basic ground truth score analysis"""
        analyzer = ScoreAnalyzer()

        # Create test pairs
        pairs = [
            GroundTruthPair(
                marc_record=Publication("Title 1", lccn="n78890351", source="MARC"),
                copyright_record=Publication("Title 1", lccn="n78890351", source="Copyright"),
                match_type="registration",
                lccn="n78890351",
            ),
            GroundTruthPair(
                marc_record=Publication("Title 2", lccn="n79123456", source="MARC"),
                copyright_record=Publication("Title 2", lccn="n79123456", source="Renewal"),
                match_type="renewal",
                lccn="n79123456",
            ),
        ]

        # Mock similarity calculation results as a dictionary
        mock_match_result = {
            "similarity_scores": {
                "title": 85.0,
                "author": 75.0,
                "publisher": 65.0,
                "combined": 80.0,
            }
        }

        # Mock the instance method
        with patch.object(analyzer, "_calculate_text_similarity", return_value=mock_match_result):
            analysis = analyzer.analyze_ground_truth_scores(pairs)

        assert analysis.total_pairs == 2
        assert analysis.registration_pairs == 1
        assert analysis.renewal_pairs == 1

        # Check that scores were collected
        assert len(analysis.title_distribution.scores) == 2
        assert len(analysis.author_distribution.scores) == 2
        assert len(analysis.publisher_distribution.scores) == 2
        assert len(analysis.combined_distribution.scores) == 2

        # All scores should be the mocked values
        assert all(score == 85.0 for score in analysis.title_distribution.scores)
        assert all(score == 75.0 for score in analysis.author_distribution.scores)

    def test_analyze_ground_truth_scores_no_match_result(self):
        """Test analysis when similarity calculation returns None"""
        analyzer = ScoreAnalyzer()

        pairs = [
            GroundTruthPair(
                marc_record=Publication("Title 1", lccn="n78890351", source="MARC"),
                copyright_record=Publication("Title 1", lccn="n78890351", source="Copyright"),
                match_type="registration",
                lccn="n78890351",
            )
        ]

        # Mock returns None (no match result)
        with patch.object(analyzer, "_calculate_text_similarity", return_value=None):
            analysis = analyzer.analyze_ground_truth_scores(pairs)

        assert analysis.total_pairs == 1
        assert len(analysis.title_distribution.scores) == 0
        assert len(analysis.author_distribution.scores) == 0

    def test_calculate_text_similarity_lccn_handling(self):
        """Test that LCCN fields are properly cleared and restored"""
        analyzer = ScoreAnalyzer()

        marc_pub = Publication("Test Title", lccn="n78890351", source="MARC")
        copyright_pub = Publication("Test Title", lccn="n78890351", source="Copyright")

        # Store original normalized LCCNs
        original_marc_lccn = marc_pub.normalized_lccn
        original_copyright_lccn = copyright_pub.normalized_lccn

        # Mock the matcher to verify LCCN is cleared during matching
        mock_matcher = MagicMock()
        mock_matcher.find_best_match_ignore_thresholds.return_value = None
        analyzer.matcher = mock_matcher

        analyzer._calculate_text_similarity(marc_pub, copyright_pub)

        # Verify matcher was called
        mock_matcher.find_best_match_ignore_thresholds.assert_called_once()

        # Verify LCCN fields were restored after matching
        assert marc_pub.normalized_lccn == original_marc_lccn
        assert copyright_pub.normalized_lccn == original_copyright_lccn

    def test_generate_analysis_report_basic(self):
        """Test basic analysis report generation"""
        analyzer = ScoreAnalyzer()

        # Create test analysis
        analysis = GroundTruthAnalysis(
            total_pairs=10,
            registration_pairs=7,
            renewal_pairs=3,
            title_distribution=ScoreDistribution("title", [80.0, 85.0, 90.0]),
            author_distribution=ScoreDistribution("author", [70.0, 75.0, 80.0]),
            publisher_distribution=ScoreDistribution("publisher", [60.0, 65.0]),
            combined_distribution=ScoreDistribution("combined", [75.0, 80.0, 85.0]),
            pairs_by_match_type={},
        )

        report = analyzer.generate_analysis_report(analysis)

        assert "LCCN Ground Truth Similarity Score Analysis" in report
        assert "Total ground truth pairs analyzed: 10" in report
        assert "Registration pairs: 7" in report
        assert "Renewal pairs: 3" in report
        assert "TITLE Similarity Scores:" in report
        assert "AUTHOR Similarity Scores:" in report
        assert "PUBLISHER Similarity Scores:" in report
        assert "COMBINED Similarity Scores:" in report

    def test_generate_analysis_report_empty_distributions(self):
        """Test report generation with empty score distributions"""
        analyzer = ScoreAnalyzer()

        analysis = GroundTruthAnalysis(
            total_pairs=0,
            registration_pairs=0,
            renewal_pairs=0,
            title_distribution=ScoreDistribution("title", []),
            author_distribution=ScoreDistribution("author", []),
            publisher_distribution=ScoreDistribution("publisher", []),
            combined_distribution=ScoreDistribution("combined", []),
            pairs_by_match_type={},
        )

        report = analyzer.generate_analysis_report(analysis)

        assert "Total ground truth pairs analyzed: 0" in report
        assert "No scores available" in report
