# tests/test_api/test_marc_copyright_analyzer_proper.py

"""Tests for the actual MarcCopyrightAnalyzer class functionality"""

# Standard library imports
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock
from unittest.mock import patch

# Local imports
from marc_pd_tool.api import AnalysisResults
from marc_pd_tool.api import MarcCopyrightAnalyzer
from marc_pd_tool.data.enums import CopyrightStatus
from tests.fixtures.publications import PublicationBuilder


class TestMarcCopyrightAnalyzerProper:
    """Test the actual MarcCopyrightAnalyzer class implementation"""

    def test_initialization_defaults(self):
        """Test analyzer initializes with default values"""
        analyzer = MarcCopyrightAnalyzer()

        assert analyzer.copyright_data is None
        assert analyzer.renewal_data is None
        assert analyzer.registration_index is None
        assert analyzer.renewal_index is None
        assert analyzer.analysis_options is None
        assert isinstance(analyzer.results, AnalysisResults)
        assert analyzer.copyright_dir == "nypl-reg/xml/"
        assert analyzer.renewal_dir == "nypl-ren/data/"
        assert analyzer.cache_dir == ".marcpd_cache"

    def test_initialization_with_config_path(self):
        """Test analyzer initialization with custom config path"""
        with TemporaryDirectory() as temp_dir:
            # Create a custom config file
            config_path = Path(temp_dir) / "custom_config.json"
            config_data = {"title_threshold": 45, "author_threshold": 35, "year_tolerance": 2}
            config_path.write_text(json.dumps(config_data))

            with patch("marc_pd_tool.api.get_config") as mock_get_config:
                mock_config = Mock()
                mock_get_config.return_value = mock_config

                analyzer = MarcCopyrightAnalyzer(config_path=str(config_path))

                # Verify get_config was called with the path
                mock_get_config.assert_called_once_with(str(config_path))
                assert analyzer.config == mock_config

    def test_initialization_with_cache_dir(self):
        """Test analyzer initialization with custom cache directory"""
        custom_cache_dir = "/tmp/custom_cache"

        with patch("marc_pd_tool.api.CacheManager") as mock_cache_manager:
            analyzer = MarcCopyrightAnalyzer(cache_dir=custom_cache_dir)

            assert analyzer.cache_dir == custom_cache_dir
            mock_cache_manager.assert_called_once_with(custom_cache_dir)

    def test_initialization_force_refresh(self):
        """Test analyzer initialization with force refresh"""
        with patch("marc_pd_tool.api.CacheManager") as mock_cache_manager:
            mock_manager_instance = Mock()
            mock_cache_manager.return_value = mock_manager_instance

            analyzer = MarcCopyrightAnalyzer(force_refresh=True)

            # Verify cache was cleared
            mock_manager_instance.clear_all_caches.assert_called_once()

    def test_analyze_marc_file_basic(self):
        """Test basic MARC file analysis"""
        analyzer = MarcCopyrightAnalyzer()

        with TemporaryDirectory() as temp_dir:
            # Create a simple MARC file
            marc_path = Path(temp_dir) / "test.marcxml"
            marc_path.write_text(
                """<?xml version="1.0"?>
            <collection xmlns="http://www.loc.gov/MARC21/slim">
                <record>
                    <leader>00000nam a2200000 a 4500</leader>
                    <datafield tag="245" ind1="0" ind2="0">
                        <subfield code="a">Test Book</subfield>
                    </datafield>
                </record>
            </collection>"""
            )

            # Mock the internal methods
            with (
                patch.object(analyzer, "_load_and_index_data") as mock_load,
                patch.object(analyzer, "analyze_marc_records") as mock_process,
            ):

                # Mock analyze_marc_records to add a publication and return it
                def add_pub(publications, options):
                    pub = PublicationBuilder.basic_us_publication()
                    analyzer.results.add_publication(pub)
                    return [pub]

                mock_process.side_effect = add_pub

                # Analyze the file
                results = analyzer.analyze_marc_file(str(marc_path))

                # Verify methods were called
                mock_load.assert_called_once()
                mock_process.assert_called_once()

                # Verify results
                assert isinstance(results, AnalysisResults)
                assert results.statistics["total_records"] == 1

    def test_analyze_marc_file_with_options(self):
        """Test MARC file analysis with custom options"""
        analyzer = MarcCopyrightAnalyzer()

        with TemporaryDirectory() as temp_dir:
            marc_path = Path(temp_dir) / "test.marcxml"
            marc_path.write_text(
                """<?xml version="1.0"?>
            <collection xmlns="http://www.loc.gov/MARC21/slim">
                <record></record>
            </collection>"""
            )

            options = {
                "us_only": True,
                "min_year": 1950,
                "max_year": 1977,
                "title_threshold": 45,
                "author_threshold": 35,
            }

            with (
                patch.object(analyzer, "_load_and_index_data") as mock_load,
                patch.object(analyzer, "analyze_marc_records") as mock_process,
            ):

                # Mock analyze_marc_records to return empty list
                mock_process.return_value = []

                results = analyzer.analyze_marc_file(str(marc_path), options=options)

                # Verify options were stored
                assert analyzer.analysis_options == options

                # Verify _load_and_index_data received options
                mock_load.assert_called_once_with(options)

    def test_analyze_marc_file_with_output_path(self):
        """Test MARC file analysis with output path generates files"""
        analyzer = MarcCopyrightAnalyzer()

        with TemporaryDirectory() as temp_dir:
            marc_path = Path(temp_dir) / "test.marcxml"
            marc_path.write_text(
                """<?xml version="1.0"?>
            <collection xmlns="http://www.loc.gov/MARC21/slim">
                <record></record>
            </collection>"""
            )

            output_path = str(Path(temp_dir) / "results")

            # Mock internal methods
            with (
                patch.object(analyzer, "_load_and_index_data"),
                patch.object(analyzer, "analyze_marc_records") as mock_analyze,
                patch.object(analyzer, "export_results") as mock_export,
            ):

                # Mock analyze_marc_records to return empty list
                mock_analyze.return_value = []

                results = analyzer.analyze_marc_file(str(marc_path), output_path=output_path)

                # Verify export was called with correct arguments
                mock_export.assert_called_once_with(
                    output_path,
                    formats=["json", "csv"],  # Default formats
                    single_file=False,  # Default value
                )

    def test_analyze_marc_file_custom_directories(self):
        """Test analysis with custom copyright and renewal directories"""
        analyzer = MarcCopyrightAnalyzer()

        with TemporaryDirectory() as temp_dir:
            marc_path = Path(temp_dir) / "test.marcxml"
            marc_path.write_text(
                """<?xml version="1.0"?>
            <collection></collection>"""
            )

            custom_copyright_dir = "/custom/copyright"
            custom_renewal_dir = "/custom/renewal"

            with (
                patch.object(analyzer, "_load_and_index_data"),
                patch.object(analyzer, "analyze_marc_records") as mock_analyze,
            ):

                # Mock analyze_marc_records to return empty list
                mock_analyze.return_value = []

                analyzer.analyze_marc_file(
                    str(marc_path),
                    copyright_dir=custom_copyright_dir,
                    renewal_dir=custom_renewal_dir,
                )

                assert analyzer.copyright_dir == custom_copyright_dir
                assert analyzer.renewal_dir == custom_renewal_dir

    def test_get_results(self):
        """Test getting analysis results"""
        analyzer = MarcCopyrightAnalyzer()

        # Add some publications to results
        pub1 = PublicationBuilder.basic_us_publication()
        pub1.copyright_status = CopyrightStatus.PD_US_NOT_RENEWED

        pub2 = PublicationBuilder.basic_us_publication()
        pub2.copyright_status = CopyrightStatus.IN_COPYRIGHT

        analyzer.results.add_publication(pub1)
        analyzer.results.add_publication(pub2)

        results = analyzer.get_results()

        assert results == analyzer.results
        assert results.statistics["total_records"] == 2
        assert len(results.publications) == 2

    def test_export_results_various_formats(self):
        """Test exporting results in various formats"""
        analyzer = MarcCopyrightAnalyzer()

        # Add a publication
        pub = PublicationBuilder.basic_us_publication()
        analyzer.results.add_publication(pub)

        with TemporaryDirectory() as temp_dir:
            output_path = str(Path(temp_dir) / "results")

            # Export with defaults should create JSON
            analyzer.export_results(output_path)
            assert Path(f"{output_path}.json").exists()

    def test_export_results_single_file_option(self):
        """Test export with single_file option"""
        analyzer = MarcCopyrightAnalyzer()

        pub = PublicationBuilder.basic_us_publication()
        analyzer.results.add_publication(pub)

        with TemporaryDirectory() as temp_dir:
            output_path = str(Path(temp_dir) / "results")

            # Export with single_file=True (default)
            analyzer.export_results(output_path, single_file=True)

            # Should create JSON file
            assert Path(f"{output_path}.json").exists()

    def test_analyze_marc_records_method(self):
        """Test the analyze_marc_records method directly"""
        analyzer = MarcCopyrightAnalyzer()

        # Create test publications
        pubs = [
            PublicationBuilder.basic_us_publication(source_id="test1"),
            PublicationBuilder.basic_us_publication(source_id="test2"),
        ]

        # Mock necessary components
        analyzer.registration_index = Mock()
        analyzer.renewal_index = Mock()
        analyzer.generic_detector = Mock()

        with patch.object(analyzer, "_process_sequentially") as mock_process:
            # Mock to add publications to results and return them
            def process_pubs(*args, **kwargs):
                for pub in pubs:
                    analyzer.results.add_publication(pub)
                return pubs

            mock_process.side_effect = process_pubs

            # Call analyze_marc_records
            result_pubs = analyzer.analyze_marc_records(pubs, {})

            # Verify processing occurred
            assert len(analyzer.results.publications) == 2
            assert result_pubs == pubs  # Should return the publications passed in

    def test_process_records_with_ground_truth(self):
        """Test processing records when ground truth is available"""
        analyzer = MarcCopyrightAnalyzer()

        # Set up mock ground truth
        # Local imports
        from marc_pd_tool.data.ground_truth import GroundTruthAnalysis

        analyzer.ground_truth_analysis = Mock(spec=GroundTruthAnalysis)

        # Create publication
        pub = PublicationBuilder.basic_us_publication()

        with (
            patch.object(analyzer, "_load_and_index_data"),
            patch.object(analyzer, "analyze_marc_records") as mock_analyze,
        ):

            # Mock analyze to add ground truth info
            def add_ground_truth(*args, **kwargs):
                analyzer.results.add_publication(pub)
                analyzer.results.ground_truth_analysis = analyzer.ground_truth_analysis

            mock_analyze.side_effect = add_ground_truth

            with TemporaryDirectory() as temp_dir:
                marc_path = Path(temp_dir) / "test.marcxml"
                marc_path.write_text('<?xml version="1.0"?><collection></collection>')

                results = analyzer.analyze_marc_file(str(marc_path))

                assert results.ground_truth_analysis is not None
