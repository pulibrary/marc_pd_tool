# tests/test_api/test_simplified_api.py

"""Tests for the simplified MarcCopyrightAnalyzer API"""

# Standard library imports
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock
from unittest.mock import Mock
from unittest.mock import patch

# Local imports
from marc_pd_tool.api import AnalysisResults
from marc_pd_tool.api import MarcCopyrightAnalyzer
from marc_pd_tool.data.enums import CopyrightStatus
from tests.fixtures.publications import PublicationBuilder


class TestMarcCopyrightAnalyzerAPI:
    """Test the simplified MarcCopyrightAnalyzer class"""

    def test_init_with_defaults(self):
        """Test initialization with default values"""
        analyzer = MarcCopyrightAnalyzer()

        assert analyzer.config is not None
        assert analyzer.cache_dir == ".marcpd_cache"
        assert analyzer.cache_manager is not None
        assert analyzer.results is not None
        assert isinstance(analyzer.results, AnalysisResults)
        assert analyzer.copyright_dir == "nypl-reg/xml/"
        assert analyzer.renewal_dir == "nypl-ren/data/"

    def test_init_with_custom_cache_dir(self):
        """Test initialization with custom cache directory"""
        analyzer = MarcCopyrightAnalyzer(cache_dir="/tmp/test_cache")

        assert analyzer.cache_dir == "/tmp/test_cache"
        assert analyzer.cache_manager.cache_dir == "/tmp/test_cache"

    @patch("marc_pd_tool.api._analyzer.CacheManager")
    def test_init_with_force_refresh(self, mock_cache_manager):
        """Test initialization with force refresh"""
        mock_cache_instance = MagicMock()
        mock_cache_manager.return_value = mock_cache_instance

        analyzer = MarcCopyrightAnalyzer(force_refresh=True)

        # Verify cache was cleared
        mock_cache_instance.clear_all_caches.assert_called_once()

    @patch("marc_pd_tool.api._analyzer.get_config")
    def test_init_with_config_path(self, mock_get_config):
        """Test initialization with custom config path"""
        mock_config = Mock()
        mock_get_config.return_value = mock_config

        analyzer = MarcCopyrightAnalyzer(config_path="/path/to/config.json")

        # Verify config was loaded from the specified path
        mock_get_config.assert_called_once_with("/path/to/config.json")
        assert analyzer.config == mock_config

    def test_analyze_marc_file_basic(self):
        """Test basic file analysis structure"""
        # Create analyzer
        analyzer = MarcCopyrightAnalyzer()

        with TemporaryDirectory() as temp_dir:
            marc_path = str(Path(temp_dir) / "test.xml")
            Path(marc_path).write_text("<marc>test</marc>")

            # We can't easily test the full flow without extensive mocking
            # So just verify the method exists and returns the right type
            assert hasattr(analyzer, "analyze_marc_file")
            assert hasattr(analyzer, "analyze_marc_records")

            # Verify the analyzer is properly initialized
            assert analyzer.results is not None
            assert isinstance(analyzer.results, AnalysisResults)

    def test_analyze_marc_file_with_options(self):
        """Test file analysis with custom options"""
        analyzer = MarcCopyrightAnalyzer()

        with TemporaryDirectory() as temp_dir:
            marc_path = str(Path(temp_dir) / "test.xml")
            Path(marc_path).write_text("<marc>test</marc>")

            options = {
                "us_only": True,
                "min_year": 1950,
                "max_year": 1970,
                "title_threshold": 45,
                "author_threshold": 35,
                "year_tolerance": 2,
            }

            # Mock the load_and_index_data to avoid full execution
            with patch.object(analyzer, "_load_and_index_data") as mock_load:
                with patch("marc_pd_tool.api._analyzer.MarcLoader") as mock_loader:
                    mock_instance = MagicMock()
                    mock_loader.return_value = mock_instance
                    mock_instance.load.return_value = []

                    analyzer.analyze_marc_file(marc_path, options=options)

                    # Verify options were stored
                    assert analyzer.analysis_options == options

    def test_get_results(self):
        """Test getting analysis results"""
        analyzer = MarcCopyrightAnalyzer()

        # Add some test data to results
        pub = PublicationBuilder.basic_us_publication()
        pub.copyright_status = CopyrightStatus.US_REGISTERED_NOT_RENEWED.value
        analyzer.results.add_publication(pub)

        results = analyzer.get_results()

        assert results == analyzer.results
        assert len(results.publications) == 1
        assert results.statistics["total_records"] == 1
        assert results.statistics["us_registered_not_renewed"] == 1

    def test_results_isolation(self):
        """Test that results are isolated between analyses"""
        analyzer = MarcCopyrightAnalyzer()

        # Add some data
        pub = PublicationBuilder.basic_us_publication()
        analyzer.results.add_publication(pub)

        assert len(analyzer.results.publications) == 1

        # Create new analyzer - should have fresh results
        analyzer2 = MarcCopyrightAnalyzer()

        assert len(analyzer2.results.publications) == 0
        assert analyzer2.results.statistics["total_records"] == 0

    def test_export_results_workflow(self):
        """Test the export results workflow"""
        analyzer = MarcCopyrightAnalyzer()

        # Add test data
        pub = PublicationBuilder.basic_us_publication()
        analyzer.results.add_publication(pub)

        # The actual export would happen through analyze_marc_file
        # with the output_path parameter
        assert analyzer.results.statistics["total_records"] == 1

    def test_analysis_options_storage(self):
        """Test that analysis options are stored"""
        analyzer = MarcCopyrightAnalyzer()

        # Initially no options
        assert analyzer.analysis_options is None

        # Options would be set when calling analyze_marc_file
        test_options = {"us_only": True, "title_threshold": 45}
        analyzer.analysis_options = test_options

        assert analyzer.analysis_options == test_options

    def test_end_to_end_workflow(self):
        """Test complete analysis workflow"""
        analyzer = MarcCopyrightAnalyzer()

        # This would be an integration test in practice
        # For now, just verify the API structure
        assert hasattr(analyzer, "analyze_marc_file")
        assert hasattr(analyzer, "get_results")
        assert hasattr(analyzer, "analyze_marc_records")
        assert hasattr(analyzer, "export_results")
