# tests/adapters/api/test_marc_copyright_analyzer_proper.py

"""Tests for the actual MarcCopyrightAnalyzer class functionality"""

# Standard library imports
from json import dumps
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock
from unittest.mock import patch

# Local imports
from marc_pd_tool.adapters.api import AnalysisResults
from marc_pd_tool.adapters.api import MarcCopyrightAnalyzer
from marc_pd_tool.application.models.config_models import AnalysisOptions
from marc_pd_tool.core.domain.enums import CopyrightStatus
from tests.fixtures.publications import PublicationBuilder


class TestMarcCopyrightAnalyzerProper:
    """Test the actual MarcCopyrightAnalyzer class implementation"""

    def test_initialization_defaults(self):
        """Test analyzer initializes with default values"""
        analyzer = MarcCopyrightAnalyzer()

        assert analyzer.copyright_data == []
        assert analyzer.renewal_data == []
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
            config_path.write_text(dumps(config_data))

            with patch("marc_pd_tool.adapters.api._analyzer.get_config") as mock_get_config:
                mock_config = Mock()
                mock_get_config.return_value = mock_config

                analyzer = MarcCopyrightAnalyzer(config_path=str(config_path))

                # Verify get_config was called with the path
                mock_get_config.assert_called_once_with(str(config_path))
                assert analyzer.config == mock_config

    def test_initialization_with_cache_dir(self):
        """Test analyzer initialization with custom cache directory"""
        custom_cache_dir = "/tmp/custom_cache"

        with patch("marc_pd_tool.adapters.api._analyzer.CacheManager") as mock_cache_manager:
            analyzer = MarcCopyrightAnalyzer(cache_dir=custom_cache_dir)

            assert analyzer.cache_dir == custom_cache_dir
            mock_cache_manager.assert_called_once_with(custom_cache_dir)

    def test_initialization_force_refresh(self):
        """Test analyzer initialization with force refresh"""
        with patch("marc_pd_tool.adapters.api._analyzer.CacheManager") as mock_cache_manager:
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

            # Mock the internal methods and MarcLoader
            with (
                patch.object(analyzer, "_load_and_index_data") as mock_load,
                patch("marc_pd_tool.adapters.api._analyzer.MarcLoader") as mock_marc_loader_class,
                patch.object(analyzer, "_process_marc_batches") as mock_process_batches,
            ):
                # Mock MarcLoader to return empty batches
                mock_loader = Mock()
                mock_loader.extract_batches_to_disk.return_value = (["batch1.pkl"], 1, 0)
                mock_marc_loader_class.return_value = mock_loader

                # Mock _process_marc_batches to add a publication
                def process_batches(batch_paths, marc_path, options):
                    pub = PublicationBuilder.basic_us_publication()
                    analyzer.results.add_publication(pub)

                mock_process_batches.side_effect = process_batches

                # Analyze the file
                results = analyzer.analyze_marc_file(str(marc_path))

                # Verify methods were called
                mock_load.assert_called_once()
                mock_loader.extract_batches_to_disk.assert_called_once()
                mock_process_batches.assert_called_once()

                # Verify results
                assert isinstance(results, AnalysisResults)
                assert results.statistics.total_records == 1

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

            options = AnalysisOptions(
                us_only=True, min_year=1950, max_year=1977, title_threshold=45, author_threshold=35
            )

            with (
                patch.object(analyzer, "_load_and_index_data") as mock_load,
                patch("marc_pd_tool.adapters.api._analyzer.MarcLoader") as mock_marc_loader_class,
                patch.object(analyzer, "_process_marc_batches") as mock_process_batches,
            ):
                # Mock MarcLoader to return empty batches
                mock_loader = Mock()
                mock_loader.extract_batches_to_disk.return_value = ([], 0, 0)
                mock_marc_loader_class.return_value = mock_loader

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
                patch("marc_pd_tool.adapters.api._analyzer.MarcLoader") as mock_marc_loader_class,
                patch.object(analyzer, "_process_marc_batches") as mock_process_batches,
                patch.object(analyzer, "export_results") as mock_export,
            ):
                # Mock MarcLoader to return at least one batch so export happens
                mock_loader = Mock()
                mock_loader.extract_batches_to_disk.return_value = (["batch1.pkl"], 1, 0)
                mock_marc_loader_class.return_value = mock_loader

                results = analyzer.analyze_marc_file(str(marc_path), output_path=output_path)

                # Verify export was called with correct arguments
                mock_export.assert_called_once_with(
                    output_path,
                    formats=["csv"],  # Default formats from AnalysisOptions
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
                patch("marc_pd_tool.adapters.api._analyzer.MarcLoader") as mock_marc_loader_class,
                patch.object(analyzer, "_process_marc_batches") as mock_process_batches,
            ):
                # Mock MarcLoader to return empty batches
                mock_loader = Mock()
                mock_loader.extract_batches_to_disk.return_value = ([], 0, 0)
                mock_marc_loader_class.return_value = mock_loader

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
        pub1.copyright_status = CopyrightStatus.US_REGISTERED_NOT_RENEWED.value

        pub2 = PublicationBuilder.basic_us_publication()
        pub2.copyright_status = CopyrightStatus.US_RENEWED.value

        analyzer.results.add_publication(pub1)
        analyzer.results.add_publication(pub2)

        results = analyzer.get_results()

        assert results == analyzer.results
        assert results.statistics.total_records == 2
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

        # Mock necessary components BEFORE calling the method
        analyzer.registration_index = Mock()
        analyzer.renewal_index = Mock()
        analyzer.generic_detector = Mock()

        # Patch logger to avoid logging issues
        with patch("marc_pd_tool.adapters.api._analyzer.logger"):
            # Patch mkdtemp to avoid creating real temp directories
            with patch("tempfile.mkdtemp") as mock_mkdtemp:
                mock_mkdtemp.return_value = "/tmp/test_temp"

                # Patch dump to avoid pickling
                with patch("pickle.dump"):
                    # Create a mock that supports context manager protocol
                    mock_open = Mock()
                    mock_file = Mock()
                    mock_open.return_value.__enter__ = Mock(return_value=mock_file)
                    mock_open.return_value.__exit__ = Mock(return_value=None)

                    # Patch open to avoid file operations
                    with patch("builtins.open", mock_open):
                        # Also patch StreamingComponent._analyze_marc_file_streaming to avoid real processing
                        with patch(
                            "marc_pd_tool.adapters.api._analyzer.StreamingComponent._analyze_marc_file_streaming"
                        ) as mock_stream:
                            # Mock to add publications to results
                            def stream_pubs(self, *args, **kwargs):
                                for pub in pubs:
                                    self.results.add_publication(pub)

                            mock_stream.side_effect = stream_pubs

                            # Call analyze_marc_records
                            result_pubs = analyzer.analyze_marc_records(pubs, AnalysisOptions())

                            # Verify processing occurred
                            assert len(analyzer.results.publications) == 2
                            assert result_pubs == pubs  # Should return the publications passed in
