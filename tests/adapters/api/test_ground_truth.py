# tests/adapters/api/test_ground_truth.py

"""Comprehensive tests for the ground truth component"""

# Standard library imports
from json import loads
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock
from unittest.mock import patch

# Third party imports
import pytest

# Local imports
from marc_pd_tool.adapters.api._ground_truth import GroundTruthComponent
from marc_pd_tool.application.models.analysis_results import AnalysisResults
from marc_pd_tool.application.models.ground_truth_stats import GroundTruthStats
from marc_pd_tool.application.processing.indexer import DataIndexer
from marc_pd_tool.core.domain.enums import CountryClassification
from marc_pd_tool.core.domain.enums import MatchType
from marc_pd_tool.core.domain.match_result import MatchResult
from marc_pd_tool.core.domain.publication import Publication
from marc_pd_tool.infrastructure.config import ConfigLoader


class MockAnalyzer(GroundTruthComponent):
    """Mock analyzer implementing GroundTruthAnalyzerProtocol and inheriting from GroundTruthComponent"""

    def __init__(self):
        self.results = AnalysisResults()
        self.copyright_dir = "nypl-reg/xml/"
        self.renewal_dir = "nypl-ren/data/"
        self.copyright_data = None
        self.renewal_data = None
        self.config = Mock(spec=ConfigLoader)
        self.config.processing = Mock()
        self.config.processing.batch_size = 100
        self.registration_index = None
        self.renewal_index = None

    def _load_and_index_data(self, options):
        """Mock implementation of data loading"""
        pass

    def _export_ground_truth_json(self, output_path):
        """Mock implementation of JSON export"""
        # Call the parent implementation for real tests
        super()._export_ground_truth_json(output_path)

    def _export_ground_truth_csv(self, output_path):
        """Mock implementation of CSV export"""
        # Call the parent implementation for real tests
        super()._export_ground_truth_csv(output_path)


class TestGroundTruthComponent:
    """Test suite for GroundTruthComponent"""

    @pytest.fixture
    def mock_analyzer(self):
        """Create a mock analyzer with required protocol attributes"""
        return MockAnalyzer()

    @pytest.fixture
    def sample_publications(self):
        """Create sample publication data for testing"""
        marc_pub = Publication(
            title="Test Book",
            author="Test Author",
            year=1960,
            publisher="Test Publisher",
            source_id="marc_001",
            lccn="60123456",
            normalized_lccn="60123456",
            country_code="xxu",
            country_classification=CountryClassification.US,
        )

        copyright_pub = Publication(
            title="Test Book Registered",
            author="Test Author",
            year=1960,
            publisher="Test Publisher Co",
            source_id="reg_001",
            lccn="60123456",
            normalized_lccn="60123456",
        )

        renewal_pub = Publication(
            title="Test Book Renewed",
            author="Test Author",
            year=1960,
            publisher="Test Publisher",
            source_id="ren_001",
            lccn="60123456",
            normalized_lccn="60123456",
        )

        return marc_pub, copyright_pub, renewal_pub

    def test_extract_ground_truth_basic(self, mock_analyzer, sample_publications):
        """Test basic ground truth extraction"""
        marc_pub, copyright_pub, renewal_pub = sample_publications

        # Set up mock data
        mock_analyzer.copyright_data = [copyright_pub]
        mock_analyzer.renewal_data = [renewal_pub]

        # Create a match result for the MARC record
        reg_match = MatchResult(
            matched_title="Test Book Registered",
            matched_author="Test Author",
            matched_publisher="Test Publisher Co",
            source_id="reg_001",
            source_type="registration",
            title_score=95.0,
            author_score=100.0,
            publisher_score=90.0,
            similarity_score=95.0,
            year_difference=0,
            match_type=MatchType.LCCN,
        )

        ren_match = MatchResult(
            matched_title="Test Book Renewed",
            matched_author="Test Author",
            matched_publisher="Test Publisher",
            source_id="ren_001",
            source_type="renewal",
            title_score=90.0,
            author_score=100.0,
            publisher_score=100.0,
            similarity_score=96.67,
            year_difference=0,
            match_type=MatchType.LCCN,
        )

        marc_pub.registration_match = reg_match
        marc_pub.renewal_match = ren_match

        # Mock the extractor
        with (
            patch("marc_pd_tool.adapters.api._ground_truth.MarcLoader") as mock_loader_class,
            patch(
                "marc_pd_tool.adapters.api._ground_truth.GroundTruthExtractor"
            ) as mock_extractor_class,
        ):

            # Set up mocks
            mock_loader = Mock()
            mock_loader_class.return_value = mock_loader
            mock_loader.extract_all_batches.return_value = [[marc_pub]]

            mock_extractor = Mock()
            mock_extractor_class.return_value = mock_extractor

            stats = GroundTruthStats(
                total_marc_records=1,
                marc_with_lccn=1,
                total_copyright_records=1,
                copyright_with_lccn=1,
                total_renewal_records=1,
                registration_matches=1,
                renewal_matches=1,
                unique_lccns_matched=1,
            )

            mock_extractor.extract_ground_truth_pairs.return_value = ([marc_pub], stats)
            mock_extractor.filter_by_year_range.return_value = [marc_pub]

            # Call the method
            result_pubs, result_stats = mock_analyzer.extract_ground_truth(
                marc_path="test.xml",
                copyright_dir="test_copyright/",
                renewal_dir="test_renewal/",
                min_year=1950,
                max_year=1970,
            )

            # Verify results
            assert len(result_pubs) == 1
            assert result_pubs[0] == marc_pub
            assert result_stats == stats

            # Verify directories were set
            assert mock_analyzer.copyright_dir == "test_copyright/"
            assert mock_analyzer.renewal_dir == "test_renewal/"

            # Verify results were stored
            assert mock_analyzer.results.ground_truth_pairs == [marc_pub]
            assert mock_analyzer.results.ground_truth_stats == stats

            # Verify loader was called with correct parameters
            mock_loader_class.assert_called_once_with(
                marc_path="test.xml", batch_size=100, min_year=1950, max_year=1970
            )

            # Verify extractor was called correctly
            mock_extractor.extract_ground_truth_pairs.assert_called_once_with(
                [[marc_pub]], [copyright_pub], [renewal_pub]
            )
            mock_extractor.filter_by_year_range.assert_called_once_with([marc_pub], 1950, 1970)

    def test_extract_ground_truth_no_existing_data(self, mock_analyzer):
        """Test extraction when no data is pre-loaded"""
        mock_analyzer.copyright_data = None
        mock_analyzer.renewal_data = None

        with (
            patch("marc_pd_tool.adapters.api._ground_truth.MarcLoader") as mock_loader_class,
            patch(
                "marc_pd_tool.adapters.api._ground_truth.GroundTruthExtractor"
            ) as mock_extractor_class,
        ):

            # Set up mocks
            mock_loader = Mock()
            mock_loader_class.return_value = mock_loader
            mock_loader.extract_all_batches.return_value = []

            mock_extractor = Mock()
            mock_extractor_class.return_value = mock_extractor

            stats = GroundTruthStats(total_marc_records=0, marc_with_lccn=0)

            mock_extractor.extract_ground_truth_pairs.return_value = ([], stats)

            # Mock _load_and_index_data to set data
            def load_data_side_effect(options):
                mock_analyzer.copyright_data = []
                mock_analyzer.renewal_data = []

            mock_analyzer._load_and_index_data = Mock(side_effect=load_data_side_effect)

            # Call the method
            result_pubs, result_stats = mock_analyzer.extract_ground_truth(marc_path="test.xml")

            # Verify _load_and_index_data was called with AnalysisOptions
            # Local imports
            from marc_pd_tool.application.models.config_models import AnalysisOptions

            mock_analyzer._load_and_index_data.assert_called_once_with(
                AnalysisOptions(min_year=None, max_year=None)
            )

            # Verify empty results
            assert result_pubs == []
            assert result_stats == stats

    def test_extract_ground_truth_with_cached_indexes(self, mock_analyzer):
        """Test extraction when indexes are loaded from cache"""
        # Set up cached indexes
        mock_index = Mock(spec=DataIndexer)
        mock_index.publications = [Publication(title="Cached Pub", source_id="cached_001")]

        mock_analyzer.registration_index = mock_index
        mock_analyzer.renewal_index = mock_index
        mock_analyzer.copyright_data = None
        mock_analyzer.renewal_data = None

        with (
            patch("marc_pd_tool.adapters.api._ground_truth.MarcLoader") as mock_loader_class,
            patch(
                "marc_pd_tool.adapters.api._ground_truth.GroundTruthExtractor"
            ) as mock_extractor_class,
        ):

            mock_loader = Mock()
            mock_loader_class.return_value = mock_loader
            mock_loader.extract_all_batches.return_value = []

            mock_extractor = Mock()
            mock_extractor_class.return_value = mock_extractor

            stats = GroundTruthStats(total_marc_records=0, marc_with_lccn=0)

            mock_extractor.extract_ground_truth_pairs.return_value = ([], stats)

            # Call the method
            mock_analyzer.extract_ground_truth(marc_path="test.xml")

            # Verify that publications were extracted from indexes
            assert mock_analyzer.copyright_data == mock_index.publications
            assert mock_analyzer.renewal_data == mock_index.publications

            # Verify extractor was called with index publications
            mock_extractor.extract_ground_truth_pairs.assert_called_once_with(
                [], mock_index.publications, mock_index.publications
            )

    def test_extract_ground_truth_no_renewals(self, mock_analyzer):
        """Test extraction when renewal data is None"""
        mock_analyzer.copyright_data = []
        mock_analyzer.renewal_data = None

        with (
            patch("marc_pd_tool.adapters.api._ground_truth.MarcLoader") as mock_loader_class,
            patch(
                "marc_pd_tool.adapters.api._ground_truth.GroundTruthExtractor"
            ) as mock_extractor_class,
        ):

            mock_loader = Mock()
            mock_loader_class.return_value = mock_loader
            mock_loader.extract_all_batches.return_value = []

            mock_extractor = Mock()
            mock_extractor_class.return_value = mock_extractor

            stats = GroundTruthStats(total_marc_records=0, marc_with_lccn=0)

            mock_extractor.extract_ground_truth_pairs.return_value = ([], stats)

            # Call the method
            mock_analyzer.extract_ground_truth(marc_path="test.xml")

            # Verify extractor was called with None for renewals
            mock_extractor.extract_ground_truth_pairs.assert_called_once_with([], [], None)

    def test_export_ground_truth_analysis_csv(self, mock_analyzer, sample_publications):
        """Test CSV export of ground truth analysis"""
        marc_pub, _, _ = sample_publications
        mock_analyzer.results.ground_truth_pairs = [marc_pub]

        with patch(
            "marc_pd_tool.adapters.exporters.ground_truth_csv_exporter.export_ground_truth_csv"
        ) as mock_export:
            # Call export with CSV format
            mock_analyzer.export_ground_truth_analysis(
                output_path="test_output", output_formats=["csv"]
            )

            # Verify CSV export was called
            mock_export.assert_called_once_with([marc_pub], "test_output")

    def test_export_ground_truth_analysis_json(self, mock_analyzer, sample_publications):
        """Test JSON export of ground truth analysis"""
        marc_pub, _, _ = sample_publications

        # Set up match results
        reg_match = MatchResult(
            matched_title="Test Book Registered",
            matched_author="Test Author",
            matched_publisher="Test Publisher Co",
            source_id="reg_001",
            source_type="registration",
            title_score=95.0,
            author_score=100.0,
            publisher_score=90.0,
            similarity_score=95.0,
            year_difference=0,
            match_type=MatchType.LCCN,
        )
        marc_pub.registration_match = reg_match

        mock_analyzer.results.ground_truth_pairs = [marc_pub]
        mock_analyzer.results.ground_truth_stats = GroundTruthStats(
            total_marc_records=1, marc_with_lccn=1, registration_matches=1, unique_lccns_matched=1
        )

        with TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_output"

            # Mock _export_ground_truth_json
            mock_analyzer._export_ground_truth_json = Mock()

            # Call export with JSON format
            mock_analyzer.export_ground_truth_analysis(
                output_path=str(output_path), output_formats=["json"]
            )

            # Verify JSON export was called
            mock_analyzer._export_ground_truth_json.assert_called_once_with(str(output_path))

    def test_export_ground_truth_analysis_multiple_formats(self, mock_analyzer):
        """Test export with multiple formats"""
        mock_analyzer.results.ground_truth_pairs = [Publication(title="Test", source_id="001")]

        with patch(
            "marc_pd_tool.adapters.exporters.ground_truth_csv_exporter.export_ground_truth_csv"
        ) as mock_csv:
            mock_analyzer._export_ground_truth_json = Mock()

            # Call export with multiple formats
            mock_analyzer.export_ground_truth_analysis(
                output_path="test_output", output_formats=["csv", "json", "xlsx", "html"]
            )

            # Verify CSV and JSON were called
            mock_csv.assert_called_once()
            mock_analyzer._export_ground_truth_json.assert_called_once()

            # XLSX and HTML should log warnings (not implemented)
            # These are tested through log output in integration tests

    def test_export_ground_truth_analysis_backward_compatibility(self, mock_analyzer):
        """Test backward compatibility with output_format parameter"""
        mock_analyzer.results.ground_truth_pairs = [Publication(title="Test", source_id="001")]

        with patch(
            "marc_pd_tool.adapters.exporters.ground_truth_csv_exporter.export_ground_truth_csv"
        ) as mock_csv:
            # Call with deprecated output_format parameter
            mock_analyzer.export_ground_truth_analysis(
                output_path="test_output", output_format="csv"  # Deprecated parameter
            )

            # Verify CSV export was called
            mock_csv.assert_called_once()

    def test_export_ground_truth_analysis_no_pairs(self, mock_analyzer):
        """Test export raises error when no ground truth pairs available"""
        mock_analyzer.results.ground_truth_pairs = []

        with pytest.raises(ValueError, match="No ground truth pairs available to export"):
            mock_analyzer.export_ground_truth_analysis(output_path="test_output")

    def test_export_ground_truth_analysis_unknown_format(self, mock_analyzer):
        """Test export with unknown format logs warning"""
        mock_analyzer.results.ground_truth_pairs = [Publication(title="Test", source_id="001")]

        with patch("marc_pd_tool.adapters.api._ground_truth.logger") as mock_logger:
            # Call with unknown format
            mock_analyzer.export_ground_truth_analysis(
                output_path="test_output", output_formats=["unknown_format"]
            )

            # Verify warning was logged
            mock_logger.warning.assert_called_once_with("Unknown export format: unknown_format")

    def test_export_ground_truth_json_implementation(self, mock_analyzer, sample_publications):
        """Test the actual JSON export implementation"""
        marc_pub, _, _ = sample_publications

        # Set up complete match results
        reg_match = MatchResult(
            matched_title="Test Book Registered",
            matched_author="Test Author",
            matched_publisher="Test Publisher Co",
            source_id="reg_001",
            source_type="registration",
            title_score=95.0,
            author_score=100.0,
            publisher_score=90.0,
            similarity_score=95.0,
            year_difference=0,
            match_type=MatchType.LCCN,
        )

        ren_match = MatchResult(
            matched_title="Test Book Renewed",
            matched_author="Test Author",
            matched_publisher="Test Publisher",
            source_id="ren_001",
            source_type="renewal",
            title_score=90.0,
            author_score=100.0,
            publisher_score=100.0,
            similarity_score=96.67,
            year_difference=0,
            match_type=MatchType.LCCN,
        )

        marc_pub.registration_match = reg_match
        marc_pub.renewal_match = ren_match

        mock_analyzer.results.ground_truth_pairs = [marc_pub]
        mock_analyzer.results.ground_truth_stats = GroundTruthStats(
            total_marc_records=1,
            marc_with_lccn=1,
            registration_matches=1,
            renewal_matches=1,
            unique_lccns_matched=1,
        )

        with TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_output"

            # Call the actual implementation
            mock_analyzer._export_ground_truth_json(str(output_path))

            # Verify file was created
            json_file = Path(f"{output_path}.json")
            assert json_file.exists()

            # Load and verify JSON content
            with open(json_file) as f:
                data = loads(f.read())

            assert "statistics" in data
            assert "ground_truth_pairs" in data

            # Check statistics
            stats = data["statistics"]
            assert stats["total_marc_records"] == 1
            assert stats["marc_with_lccn"] == 1
            assert stats["registration_matches"] == 1
            assert stats["renewal_matches"] == 1

            # Check ground truth pairs
            pairs = data["ground_truth_pairs"]
            assert len(pairs) == 1

            pair = pairs[0]
            assert pair["marc_record"]["title"] == "Test Book"
            assert pair["marc_record"]["author"] == "Test Author"
            assert pair["marc_record"]["lccn"] == "60123456"

            # Check matches
            matches = pair["matches"]
            assert len(matches) == 2  # One registration, one renewal

            reg_match_data = matches[0]
            assert reg_match_data["match_type"] == "registration"
            assert reg_match_data["title"] == "Test Book Registered"
            assert reg_match_data["scores"]["title"] == 95.0

            ren_match_data = matches[1]
            assert ren_match_data["match_type"] == "renewal"
            assert ren_match_data["title"] == "Test Book Renewed"
            assert ren_match_data["scores"]["title"] == 90.0

    def test_export_ground_truth_json_no_matches(self, mock_analyzer, sample_publications):
        """Test JSON export when publication has no matches"""
        marc_pub, _, _ = sample_publications
        marc_pub.registration_match = None
        marc_pub.renewal_match = None

        mock_analyzer.results.ground_truth_pairs = [marc_pub]
        mock_analyzer.results.ground_truth_stats = GroundTruthStats(
            total_marc_records=1, marc_with_lccn=1
        )

        with TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_output"

            # Call the actual implementation
            mock_analyzer._export_ground_truth_json(str(output_path))

            # Load and verify JSON content
            json_file = Path(f"{output_path}.json")
            with open(json_file) as f:
                data = loads(f.read())

            # Check that matches is empty
            pairs = data["ground_truth_pairs"]
            assert len(pairs) == 1
            assert pairs[0]["matches"] == []

    def test_export_ground_truth_json_no_stats(self, mock_analyzer, sample_publications):
        """Test JSON export when no stats are available"""
        marc_pub, _, _ = sample_publications

        mock_analyzer.results.ground_truth_pairs = [marc_pub]
        mock_analyzer.results.ground_truth_stats = None

        with TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_output"

            # Call the actual implementation
            mock_analyzer._export_ground_truth_json(str(output_path))

            # Load and verify JSON content
            json_file = Path(f"{output_path}.json")
            with open(json_file) as f:
                data = loads(f.read())

            # Check that statistics have default values
            stats = data["statistics"]
            assert stats["total_marc_records"] == 0
            assert stats["marc_with_lccn"] == 0
            assert stats["marc_lccn_coverage"] == 0.0

    def test_export_ground_truth_json_file_extension(self, mock_analyzer):
        """Test JSON export handles .json extension correctly"""
        mock_analyzer.results.ground_truth_pairs = [Publication(title="Test", source_id="001")]
        mock_analyzer.results.ground_truth_stats = None

        with TemporaryDirectory() as tmpdir:
            # Test with .json extension already present
            output_path = Path(tmpdir) / "test_output.json"

            mock_analyzer._export_ground_truth_json(str(output_path))

            # Verify file was created without double extension
            assert output_path.exists()
            assert not Path(f"{output_path}.json").exists()

    def test_export_ground_truth_csv_implementation(self, mock_analyzer, sample_publications):
        """Test CSV export delegates to the exporter module"""
        marc_pub, _, _ = sample_publications
        mock_analyzer.results.ground_truth_pairs = [marc_pub]

        with patch(
            "marc_pd_tool.adapters.exporters.ground_truth_csv_exporter.export_ground_truth_csv"
        ) as mock_export:
            # Call the CSV export implementation
            mock_analyzer._export_ground_truth_csv("test_output.csv")

            # Verify delegation to the exporter
            mock_export.assert_called_once_with([marc_pub], "test_output.csv")

    def test_export_ground_truth_csv_no_pairs_warning(self, mock_analyzer):
        """Test CSV export logs warning when no pairs available"""
        mock_analyzer.results.ground_truth_pairs = None

        with patch("marc_pd_tool.adapters.api._ground_truth.logger") as mock_logger:
            # Call the CSV export implementation
            mock_analyzer._export_ground_truth_csv("test_output.csv")

            # Verify warning was logged
            mock_logger.warning.assert_called_once_with(
                "No ground truth pairs available for CSV export"
            )

    def test_export_ground_truth_json_no_pairs_raises(self, mock_analyzer):
        """Test _export_ground_truth_json raises when called directly with no pairs"""
        mock_analyzer.results.ground_truth_pairs = None

        with pytest.raises(ValueError, match="No ground truth pairs available"):
            # Override the mock to call the real implementation
            GroundTruthComponent._export_ground_truth_json(mock_analyzer, "test.json")

    def test_protocol_compliance(self):
        """Test that MockAnalyzer implements GroundTruthAnalyzerProtocol correctly"""
        # This test ensures our mock properly implements the protocol
        analyzer = MockAnalyzer()

        # Check all required attributes exist
        assert hasattr(analyzer, "results")
        assert hasattr(analyzer, "copyright_dir")
        assert hasattr(analyzer, "renewal_dir")
        assert hasattr(analyzer, "copyright_data")
        assert hasattr(analyzer, "renewal_data")
        assert hasattr(analyzer, "config")
        assert hasattr(analyzer, "registration_index")
        assert hasattr(analyzer, "renewal_index")

        # Check required methods exist
        assert callable(analyzer._load_and_index_data)
        assert callable(analyzer._export_ground_truth_json)

    def test_edge_case_empty_batches(self, mock_analyzer):
        """Test handling of empty MARC batches"""
        with (
            patch("marc_pd_tool.adapters.api._ground_truth.MarcLoader") as mock_loader_class,
            patch(
                "marc_pd_tool.adapters.api._ground_truth.GroundTruthExtractor"
            ) as mock_extractor_class,
        ):

            mock_loader = Mock()
            mock_loader_class.return_value = mock_loader
            mock_loader.extract_all_batches.return_value = []  # Empty batches

            mock_extractor = Mock()
            mock_extractor_class.return_value = mock_extractor

            stats = GroundTruthStats(total_marc_records=0, marc_with_lccn=0)

            mock_extractor.extract_ground_truth_pairs.return_value = ([], stats)

            # Should not raise an error
            result_pubs, result_stats = mock_analyzer.extract_ground_truth(marc_path="test.xml")

            assert result_pubs == []
            assert result_stats.total_marc_records == 0

    def test_year_filter_none_values(self, mock_analyzer):
        """Test that None year filters don't cause issues"""
        with (
            patch("marc_pd_tool.adapters.api._ground_truth.MarcLoader") as mock_loader_class,
            patch(
                "marc_pd_tool.adapters.api._ground_truth.GroundTruthExtractor"
            ) as mock_extractor_class,
        ):

            mock_loader = Mock()
            mock_loader_class.return_value = mock_loader
            mock_loader.extract_all_batches.return_value = []

            mock_extractor = Mock()
            mock_extractor_class.return_value = mock_extractor

            stats = GroundTruthStats(total_marc_records=0, marc_with_lccn=0)

            mock_extractor.extract_ground_truth_pairs.return_value = ([], stats)

            # Test with None values (should not call filter_by_year_range)
            mock_analyzer.extract_ground_truth(marc_path="test.xml", min_year=None, max_year=None)

            # filter_by_year_range should not be called when both are None
            mock_extractor.filter_by_year_range.assert_not_called()

    def test_partial_year_filter(self, mock_analyzer):
        """Test year filtering with only min or max specified"""
        with (
            patch("marc_pd_tool.adapters.api._ground_truth.MarcLoader") as mock_loader_class,
            patch(
                "marc_pd_tool.adapters.api._ground_truth.GroundTruthExtractor"
            ) as mock_extractor_class,
        ):

            mock_loader = Mock()
            mock_loader_class.return_value = mock_loader
            mock_loader.extract_all_batches.return_value = []

            mock_extractor = Mock()
            mock_extractor_class.return_value = mock_extractor

            stats = GroundTruthStats(total_marc_records=0, marc_with_lccn=0)

            mock_extractor.extract_ground_truth_pairs.return_value = ([], stats)
            mock_extractor.filter_by_year_range.return_value = []

            # Test with only min_year
            mock_analyzer.extract_ground_truth(marc_path="test.xml", min_year=1950, max_year=None)

            mock_extractor.filter_by_year_range.assert_called_with([], 1950, None)

            # Reset and test with only max_year
            mock_extractor.reset_mock()

            mock_analyzer.extract_ground_truth(marc_path="test.xml", min_year=None, max_year=1970)

            mock_extractor.filter_by_year_range.assert_called_with([], None, 1970)
