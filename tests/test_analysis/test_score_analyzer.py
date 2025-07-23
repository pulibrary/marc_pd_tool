# tests/test_analysis/test_score_analyzer.py

"""Test similarity score analysis for ground truth pairs"""

# Standard library imports
from pathlib import Path
import sys
from unittest.mock import MagicMock
from unittest.mock import patch

# Third party imports
import pytest

# Add scripts directory to path for analysis module imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
# Third party imports
from analysis.ground_truth_extractor import GroundTruthPair
from analysis.score_analyzer import GroundTruthAnalysis
from analysis.score_analyzer import ScoreAnalyzer
from analysis.score_analyzer import ScoreDistribution

# Local imports
from marc_pd_tool.data.publication import Publication
from marc_pd_tool.processing.matching_engine import DataMatcher


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
        assert dist.std_dev == pytest.approx(30.28, abs=0.1)
        assert dist.min_score == 10.0
        assert dist.max_score == 100.0

        # Test percentiles
        assert dist.percentile_5 == pytest.approx(14.5, abs=0.1)
        assert dist.percentile_25 == pytest.approx(32.5, abs=0.1)
        assert dist.percentile_75 == pytest.approx(77.5, abs=0.1)
        assert dist.percentile_95 == pytest.approx(95.5, abs=0.1)


class TestGroundTruthAnalysis:
    """Test the GroundTruthAnalysis dataclass"""

    def test_recommended_thresholds_default(self):
        """Test getting recommended thresholds with default percentile"""
        title_scores = [60.0, 70.0, 80.0, 90.0, 100.0]
        author_scores = [50.0, 60.0, 70.0, 80.0, 90.0]

        analysis = GroundTruthAnalysis(
            total_pairs=5,
            registration_pairs=3,
            renewal_pairs=2,
            title_distribution=ScoreDistribution("title", title_scores),
            author_distribution=ScoreDistribution("author", author_scores),
            publisher_distribution=ScoreDistribution("publisher", []),
            combined_distribution=ScoreDistribution("combined", [75.0, 85.0]),
            pairs_by_match_type={},
        )

        thresholds = analysis.get_recommended_thresholds()

        assert "title" in thresholds
        assert "author" in thresholds
        assert "combined" in thresholds
        assert "publisher" not in thresholds  # No scores available

        # 5th percentile should be conservative
        assert thresholds["title"] == pytest.approx(62.0, abs=1.0)
        assert thresholds["author"] == pytest.approx(52.0, abs=1.0)

    def test_recommended_thresholds_custom_percentile(self):
        """Test getting recommended thresholds with custom percentile"""
        title_scores = [60.0, 70.0, 80.0, 90.0, 100.0]

        analysis = GroundTruthAnalysis(
            total_pairs=5,
            registration_pairs=5,
            renewal_pairs=0,
            title_distribution=ScoreDistribution("title", title_scores),
            author_distribution=ScoreDistribution("author", []),
            publisher_distribution=ScoreDistribution("publisher", []),
            combined_distribution=ScoreDistribution("combined", []),
            pairs_by_match_type={},
        )

        thresholds = analysis.get_recommended_thresholds(percentile=25)

        assert thresholds["title"] == pytest.approx(70.0, abs=1.0)


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
        assert "RECOMMENDED THRESHOLDS:" in report
        assert "Conservative (5th percentile):" in report
        assert "Moderate (10th percentile):" in report

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

    def test_compare_algorithms(self):
        """Test algorithm comparison functionality"""
        analyzer = ScoreAnalyzer()

        pairs = [
            GroundTruthPair(
                marc_record=Publication("Title 1", lccn="n78890351", source="MARC"),
                copyright_record=Publication("Title 1", lccn="n78890351", source="Copyright"),
                match_type="registration",
                lccn="n78890351",
            )
        ]

        # Mock analysis results
        fuzzy_analysis = MagicMock()
        word_analysis = MagicMock()

        fuzzy_matcher = MagicMock()
        word_matcher = MagicMock()

        with patch.object(
            analyzer, "analyze_ground_truth_scores", side_effect=[fuzzy_analysis, word_analysis]
        ):
            comparison = analyzer.compare_algorithms(pairs, fuzzy_matcher, word_matcher)

        assert "fuzzy_string" in comparison
        assert "word_based" in comparison
        assert comparison["fuzzy_string"] is fuzzy_analysis
        assert comparison["word_based"] is word_analysis

        # Verify analyze was called twice - removed since we're using with statement

    def test_export_score_data(self):
        """Test exporting score data to CSV"""
        analyzer = ScoreAnalyzer()

        # Create test pair
        pair = GroundTruthPair(
            marc_record=Publication(
                "MARC Title",
                author="MARC Author",
                publisher="MARC Pub",
                lccn="n78890351",
                source="MARC",
            ),
            copyright_record=Publication(
                "Copyright Title",
                author="Copyright Author",
                publisher="Copyright Pub",
                lccn="n78890351",
                source="Copyright",
            ),
            match_type="registration",
            lccn="n78890351",
        )

        analysis = GroundTruthAnalysis(
            total_pairs=1,
            registration_pairs=1,
            renewal_pairs=0,
            title_distribution=ScoreDistribution("title", [85.0]),
            author_distribution=ScoreDistribution("author", [75.0]),
            publisher_distribution=ScoreDistribution("publisher", [65.0]),
            combined_distribution=ScoreDistribution("combined", [80.0]),
            pairs_by_match_type={"registration": [pair]},
        )

        # Mock similarity calculation as a dictionary
        mock_match_result = {
            "similarity_scores": {
                "title": 85.0,
                "author": 75.0,
                "publisher": 65.0,
                "combined": 80.0,
            }
        }

        # Mock the file path to use temporary file for testing
        # Standard library imports
        import os
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".csv") as tmp_file:
            test_output_path = tmp_file.name

        try:
            with patch.object(
                analyzer, "_calculate_text_similarity", return_value=mock_match_result
            ):
                analyzer.export_score_data(analysis, test_output_path)

            # Verify file was created and contains expected data
            assert os.path.exists(test_output_path)

            with open(test_output_path, "r") as f:
                lines = f.readlines()

            # Should have header + 1 data row
            assert len(lines) == 2

            # Check header
            header = lines[0].strip()
            expected_header = "pair_index,match_type,lccn,marc_title,copyright_title,title_score,marc_author,copyright_author,author_score,marc_publisher,copyright_publisher,publisher_score,combined_score"
            assert header == expected_header

            # Check data row (note: Publication model normalizes text to lowercase)
            data_row = lines[1].strip()
            expected_data = "0,registration,n78890351,marc title,copyright title,85.0,marc author,copyright author,75.0,marc pub,copyright pub,65.0,80.0"
            assert data_row == expected_data

        finally:
            # Clean up temporary file
            if os.path.exists(test_output_path):
                os.unlink(test_output_path)
