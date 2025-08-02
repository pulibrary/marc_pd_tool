# tests/test_processing/test_score_analyzer_comprehensive.py

"""Comprehensive tests for score_analyzer.py to achieve 100% coverage"""

# Standard library imports
from unittest.mock import Mock
from unittest.mock import patch
from unittest.mock import MagicMock

# Third party imports
import pytest

# Local imports
from marc_pd_tool.processing.score_analyzer import ScoreAnalyzer
from marc_pd_tool.processing.matching_engine import DataMatcher
from marc_pd_tool.processing.text_processing import GenericTitleDetector
from marc_pd_tool.data.ground_truth import GroundTruthPair
from marc_pd_tool.data.ground_truth import GroundTruthAnalysis
from marc_pd_tool.data.ground_truth import ScoreDistribution
from marc_pd_tool.data.publication import Publication


class TestScoreAnalyzerComprehensive:
    """Comprehensive tests for ScoreAnalyzer"""
    
    def test_init_with_default_matcher(self):
        """Test initialization with default matcher"""
        analyzer = ScoreAnalyzer()
        assert analyzer.logger is not None
        assert analyzer.logger.name == "ScoreAnalyzer"
        assert isinstance(analyzer.matcher, DataMatcher)
        assert isinstance(analyzer.generic_detector, GenericTitleDetector)
    
    def test_init_with_custom_matcher(self):
        """Test initialization with custom matcher"""
        mock_matcher = Mock(spec=DataMatcher)
        analyzer = ScoreAnalyzer(matcher=mock_matcher)
        assert analyzer.matcher == mock_matcher
        assert isinstance(analyzer.generic_detector, GenericTitleDetector)
    
    def test_analyze_ground_truth_scores_basic(self):
        """Test basic score analysis for ground truth pairs"""
        analyzer = ScoreAnalyzer()
        
        # Create test ground truth pairs
        marc1 = Publication(
            title="Test Book One",
            author="Author One",
            publisher="Publisher One",
            pub_date="1950",
            source_id="m001",
            lccn="50001"
        )
        marc1.normalized_lccn = "50001"
        marc1.year = 1950
        
        copyright1 = Publication(
            title="Test Book One",
            author="Author One",
            publisher="Publisher One",
            pub_date="1950",
            source_id="c001",
            lccn="50001"
        )
        copyright1.normalized_lccn = "50001"
        copyright1.year = 1950
        
        marc2 = Publication(
            title="Test Book Two",
            author="Author Two",
            publisher="Publisher Two",
            pub_date="1960",
            source_id="m002",
            lccn="60001"
        )
        marc2.normalized_lccn = "60001"
        marc2.year = 1960
        
        copyright2 = Publication(
            title="Test Book Two Modified",
            author="Author Two",
            publisher="Publisher Two Inc",
            pub_date="1960",
            source_id="c002",
            lccn="60001"
        )
        copyright2.normalized_lccn = "60001"
        copyright2.year = 1960
        
        pairs = [
            GroundTruthPair(
                marc_record=marc1,
                copyright_record=copyright1,
                match_type="registration",
                lccn="50001"
            ),
            GroundTruthPair(
                marc_record=marc2,
                copyright_record=copyright2,
                match_type="registration",
                lccn="60001"
            )
        ]
        
        # Analyze scores
        analysis = analyzer.analyze_ground_truth_scores(pairs)
        
        # Check analysis structure
        assert analysis is not None
        assert analysis.total_pairs == 2
        assert analysis.registration_pairs == 2
        assert analysis.renewal_pairs == 0
        
        # Check score distributions
        assert isinstance(analysis.title_distribution, ScoreDistribution)
        assert analysis.title_distribution.field_name == "title"
        assert len(analysis.title_distribution.scores) == 2
        assert 100.0 in analysis.title_distribution.scores  # Perfect match for first pair
        assert any(score < 100.0 for score in analysis.title_distribution.scores)  # Modified title for second
        
        # Check other distributions exist
        assert isinstance(analysis.author_distribution, ScoreDistribution)
        assert isinstance(analysis.publisher_distribution, ScoreDistribution)
        assert isinstance(analysis.combined_distribution, ScoreDistribution)
    
    def test_analyze_with_renewal_pairs(self):
        """Test analysis with renewal type pairs"""
        analyzer = ScoreAnalyzer()
        
        # Create renewal pair
        marc = Publication(
            title="Renewal Book",
            author="Renewal Author",
            pub_date="1955",
            source_id="m001",
            lccn="55001"
        )
        marc.normalized_lccn = "55001"
        marc.year = 1955
        
        renewal = Publication(
            title="Renewal Book",
            author="Renewal Author",
            pub_date="1955",
            source_id="r001",
            lccn="55001"
        )
        renewal.normalized_lccn = "55001"
        renewal.year = 1955
        
        pairs = [
            GroundTruthPair(
                marc_record=marc,
                copyright_record=renewal,
                match_type="renewal",
                lccn="55001"
            )
        ]
        
        analysis = analyzer.analyze_ground_truth_scores(pairs)
        
        assert analysis.registration_pairs == 0
        assert analysis.renewal_pairs == 1
        assert analysis.total_pairs == 1
    
    def test_analyze_with_mixed_pairs(self):
        """Test analysis with both registration and renewal pairs"""
        analyzer = ScoreAnalyzer()
        
        # Create registration pair
        marc1 = Publication(
            title="Book One",
            author="Author One",
            pub_date="1950",
            source_id="m001",
            lccn="50001"
        )
        marc1.normalized_lccn = "50001"
        marc1.year = 1950
        
        copyright1 = Publication(
            title="Book One",
            author="Author One",
            pub_date="1950",
            source_id="c001",
            lccn="50001"
        )
        copyright1.normalized_lccn = "50001"
        copyright1.year = 1950
        
        # Create renewal pair
        marc2 = Publication(
            title="Book Two",
            author="Author Two",
            pub_date="1955",
            source_id="m002",
            lccn="55001"
        )
        marc2.normalized_lccn = "55001"
        marc2.year = 1955
        
        renewal2 = Publication(
            title="Book Two",
            author="Author Two",
            pub_date="1955",
            source_id="r002",
            lccn="55001"
        )
        renewal2.normalized_lccn = "55001"
        renewal2.year = 1955
        
        pairs = [
            GroundTruthPair(
                marc_record=marc1,
                copyright_record=copyright1,
                match_type="registration",
                lccn="50001"
            ),
            GroundTruthPair(
                marc_record=marc2,
                copyright_record=renewal2,
                match_type="renewal",
                lccn="55001"
            )
        ]
        
        analysis = analyzer.analyze_ground_truth_scores(pairs)
        
        assert analysis.registration_pairs == 1
        assert analysis.renewal_pairs == 1
        assert analysis.total_pairs == 2
        assert "registration" in analysis.pairs_by_match_type
        assert "renewal" in analysis.pairs_by_match_type
    
    def test_analyze_with_failed_matches(self):
        """Test analysis when some matches fail (return None)"""
        analyzer = ScoreAnalyzer()
        
        # Create pair that will fail matching
        marc = Publication(
            title="Completely Different Title",
            author="Wrong Author",
            pub_date="1950",
            source_id="m001",
            lccn="50001"
        )
        marc.normalized_lccn = "50001"
        marc.year = 1950
        
        copyright = Publication(
            title="Original Title",
            author="Correct Author",
            pub_date="1950",
            source_id="c001",
            lccn="50001"
        )
        copyright.normalized_lccn = "50001"
        copyright.year = 1950
        
        pairs = [
            GroundTruthPair(
                marc_record=marc,
                copyright_record=copyright,
                match_type="registration",
                lccn="50001"
            )
        ]
        
        # Mock the matcher to return None (failed match)
        with patch.object(analyzer.matcher, 'find_best_match_ignore_thresholds', return_value=None):
            analysis = analyzer.analyze_ground_truth_scores(pairs)
        
        # Since match failed, scores should be empty or very low
        assert analysis.total_pairs == 1
        # Check individual distributions
        assert len(analysis.title_distribution.scores) == 0 or all(s < 50 for s in analysis.title_distribution.scores)
    
    def test_analyze_empty_pairs(self):
        """Test analysis with empty ground truth pairs"""
        analyzer = ScoreAnalyzer()
        
        analysis = analyzer.analyze_ground_truth_scores([])
        
        assert analysis.total_pairs == 0
        assert analysis.registration_pairs == 0
        assert analysis.renewal_pairs == 0
        assert len(analysis.title_distribution.scores) == 0
        assert len(analysis.author_distribution.scores) == 0
        assert len(analysis.publisher_distribution.scores) == 0
        assert len(analysis.combined_distribution.scores) == 0
    
    def test_generate_analysis_report(self):
        """Test analysis report generation"""
        analyzer = ScoreAnalyzer()
        
        # Create a comprehensive analysis
        distributions = [
            ScoreDistribution(
                field_name="title",
                scores=[100.0, 95.0, 90.0, 85.0, 80.0]
            ),
            ScoreDistribution(
                field_name="author",
                scores=[100.0, 90.0, 80.0, 70.0, 60.0]
            ),
            ScoreDistribution(
                field_name="publisher",
                scores=[90.0, 80.0, 70.0, 60.0, 50.0]
            ),
            ScoreDistribution(
                field_name="combined",
                scores=[95.0, 85.0, 75.0, 65.0, 55.0]
            )
        ]
        
        analysis = GroundTruthAnalysis(
            total_pairs=5,
            registration_pairs=3,
            renewal_pairs=2,
            title_distribution=distributions[0],
            author_distribution=distributions[1],
            publisher_distribution=distributions[2],
            combined_distribution=distributions[3],
            pairs_by_match_type={
                "registration": [],
                "renewal": []
            }
        )
        
        report = analyzer.generate_analysis_report(analysis)
        
        # Check report contains expected sections
        assert "LCCN Ground Truth Similarity Score Analysis" in report
        assert "Total ground truth pairs analyzed: 5" in report
        assert "Registration pairs: 3" in report
        assert "Renewal pairs: 2" in report
        assert "TITLE Similarity Scores:" in report
        assert "AUTHOR Similarity Scores:" in report
        assert "PUBLISHER Similarity Scores:" in report
        assert "COMBINED Similarity Scores:" in report
        assert "Mean:" in report
        assert "Median:" in report
        assert "5th percentile:" in report
    
    def test_generate_analysis_report_with_failed_matches(self):
        """Test report generation when there are failed matches"""
        analyzer = ScoreAnalyzer()
        
        distributions = [
            ScoreDistribution(field_name="title", scores=[90.0, 80.0]),
            ScoreDistribution(field_name="author", scores=[85.0, 75.0]),
            ScoreDistribution(field_name="publisher", scores=[80.0, 70.0]),
            ScoreDistribution(field_name="combined", scores=[85.0, 75.0])
        ]
        
        analysis = GroundTruthAnalysis(
            total_pairs=5,
            registration_pairs=2,
            renewal_pairs=0,
            title_distribution=distributions[0],
            author_distribution=distributions[1],
            publisher_distribution=distributions[2],
            combined_distribution=distributions[3],
            pairs_by_match_type={"registration": []}
        )
        
        report = analyzer.generate_analysis_report(analysis)
        
        # The report doesn't show failed matches, just total pairs
        assert "Total ground truth pairs analyzed: 5" in report
        assert "Registration pairs: 2" in report
    
    def test_generate_report_with_empty_distributions(self):
        """Test report generation when distributions are empty"""
        analyzer = ScoreAnalyzer()
        
        # Create analysis with empty distributions
        empty_dist = ScoreDistribution(field_name="empty", scores=[])
        
        analysis = GroundTruthAnalysis(
            total_pairs=0,
            registration_pairs=0,
            renewal_pairs=0,
            title_distribution=empty_dist,
            author_distribution=empty_dist,
            publisher_distribution=empty_dist,
            combined_distribution=empty_dist,
            pairs_by_match_type={}
        )
        
        report = analyzer.generate_analysis_report(analysis)
        
        # Should contain "No scores available" for each empty distribution
        assert "No scores available" in report
        assert report.count("No scores available") == 4  # One for each distribution
    
    def test_analyze_with_generic_title_detection(self):
        """Test analysis includes generic title detection"""
        analyzer = ScoreAnalyzer()
        
        # Create pair with generic title
        marc = Publication(
            title="Collected Works",  # Generic title
            author="Author Name",
            pub_date="1950",
            source_id="m001",
            lccn="50001"
        )
        marc.normalized_lccn = "50001"
        marc.year = 1950
        
        copyright = Publication(
            title="Collected Works",
            author="Author Name",
            pub_date="1950",
            source_id="c001",
            lccn="50001"
        )
        copyright.normalized_lccn = "50001"
        copyright.year = 1950
        
        pairs = [
            GroundTruthPair(
                marc_record=marc,
                copyright_record=copyright,
                match_type="registration",
                lccn="50001"
            )
        ]
        
        # The analyzer should pass the generic detector to find_best_match_ignore_thresholds
        analysis = analyzer.analyze_ground_truth_scores(pairs)
        
        # Should complete without error
        assert analysis.total_pairs == 1
        assert len(analysis.title_distribution.scores) == 1  # title scores