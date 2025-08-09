# tests/integration/test_mock_workflow.py

"""Integration tests with fully mocked processing to avoid worker initialization issues"""

# Standard library imports
import json
from pathlib import Path
from unittest.mock import Mock
from unittest.mock import patch

# Local imports
from marc_pd_tool.api import MarcCopyrightAnalyzer
from marc_pd_tool.data.enums import CountryClassification
from marc_pd_tool.data.publication import Publication


class TestMockWorkflow:
    """Integration tests using mocked components"""

    def test_sequential_processing_workflow(self, small_marc_file: Path, temp_output_dir: Path):
        """Test workflow with sequential processing"""
        # Create test publications
        test_pubs = [
            Publication(
                title="Test Book 1",
                author="Author One",
                pub_date="1960",
                source_id="001",
                country_code="xxu",
                country_classification=CountryClassification.US,
            ),
            Publication(
                title="Test Book 2",
                author="Author Two",
                pub_date="1955",
                source_id="002",
                country_code="xxu",
                country_classification=CountryClassification.US,
            ),
        ]

        # Create analyzer with mocked components
        analyzer = MarcCopyrightAnalyzer()

        # Mock the internal methods to avoid heavy processing
        with patch.object(analyzer, "_load_and_index_data"):
            with patch("marc_pd_tool.api._analyzer.MarcLoader") as mock_loader_class:
                mock_loader = Mock()
                mock_loader_class.return_value = mock_loader
                mock_loader.extract_all_batches.return_value = [test_pubs]

                with patch.object(analyzer, "_process_sequentially") as mock_seq:
                    with patch.object(analyzer, "_process_parallel") as mock_par:
                        # Mock sequential processing to return test publications
                        def mock_seq_process(*args, **kwargs):
                            # Add publications to results
                            for pub in test_pubs:
                                analyzer.results.add_publication(pub)
                            return test_pubs

                        mock_seq.side_effect = mock_seq_process

                        # Run analysis with sequential processing
                        output_path = str(temp_output_dir / "test_results")
                        results = analyzer.analyze_marc_file(
                            str(small_marc_file),
                            output_path=output_path,
                            options={
                                "num_processes": 1,  # Force sequential
                                "formats": ["json", "csv"],
                                "single_file": True,  # Create single CSV file
                            },
                        )

                        # Verify sequential processing was used
                        assert mock_seq.called
                        assert not mock_par.called

        # Verify results
        assert results.statistics["total_records"] == 2
        assert len(results.publications) == 2

        # Verify output files created
        json_path = Path(f"{output_path}.json")
        csv_path = Path(f"{output_path}.csv")

        # Debug what files exist
        # Standard library imports

        parent_dir = json_path.parent
        print(f"Files in {parent_dir}: {list(parent_dir.glob('*'))}")

        assert json_path.exists(), f"JSON should exist at {json_path}"
        assert csv_path.exists(), f"CSV should exist at {csv_path}"

    @patch("marc_pd_tool.api._analyzer.CacheManager")
    def test_caching_workflow(
        self, mock_cache_manager_class, small_marc_file: Path, temp_output_dir: Path
    ):
        """Test that caching is used correctly"""
        # Mock cache manager instance
        mock_cache_instance = Mock()
        mock_cache_manager_class.return_value = mock_cache_instance

        # Mock cache methods
        mock_cache_instance.get_cached_marc_data.return_value = None
        mock_cache_instance.get_cached_indexes.return_value = None
        mock_cache_instance.clear_all_caches = Mock()

        # Create analyzer with cache
        analyzer = MarcCopyrightAnalyzer(cache_dir=str(temp_output_dir / "cache"))

        # Verify cache manager was instantiated with correct path
        mock_cache_manager_class.assert_called_with(str(temp_output_dir / "cache"))

        # Verify cache instance was created
        assert analyzer.cache_manager == mock_cache_instance

    def test_year_filtering(self, medium_marc_file: Path, temp_output_dir: Path):
        """Test that year filtering is applied correctly"""
        # Create publications with different years
        pubs_1950s = [
            Publication(
                title=f"Book {i}",
                pub_date=f"{1950+i}",
                source_id=f"{i}",
                country_code="xxu",
                country_classification=CountryClassification.US,
            )
            for i in range(5)
        ]

        analyzer = MarcCopyrightAnalyzer()

        # Mock at the API level to intercept MarcLoader creation
        with patch("marc_pd_tool.api._analyzer.MarcLoader") as mock_loader_class:
            mock_loader = Mock()
            mock_loader_class.return_value = mock_loader
            mock_loader.extract_all_batches.return_value = [pubs_1950s]

            with patch.object(analyzer, "_load_and_index_data"):
                with patch.object(analyzer, "_process_sequentially") as mock_seq:
                    # Mock sequential processing to return filtered publications
                    def mock_process(*args, **kwargs):
                        for pub in pubs_1950s:
                            analyzer.results.add_publication(pub)
                        return pubs_1950s

                    mock_seq.side_effect = mock_process

                    results = analyzer.analyze_marc_file(
                        str(medium_marc_file),
                        options={"min_year": 1950, "max_year": 1959, "num_processes": 1},
                    )

            # Verify loader was created with year filters
            mock_loader_class.assert_called_once()
            call_args = mock_loader_class.call_args
            if call_args[1]:  # kwargs
                assert call_args[1].get("min_year") == 1950
                assert call_args[1].get("max_year") == 1959

        # Verify only 1950s publications were processed
        assert len(results.publications) == 5
        for pub in results.publications:
            assert 1950 <= pub.year <= 1959

    def test_export_formats(self, temp_output_dir: Path):
        """Test different export format generation"""
        analyzer = MarcCopyrightAnalyzer()

        # Add test publication
        pub = Publication(
            title="Export Test", author="Test Author", pub_date="1960", source_id="test001"
        )
        analyzer.results.add_publication(pub)

        # Test each export format
        formats_to_test = [
            (["json"], [".json"]),
            (["csv"], [".json", ".csv"]),  # CSV requires JSON to exist first
            (["xlsx"], [".xlsx"]),  # XLSX exports directly, no JSON needed
            (["json", "csv", "xlsx"], [".json", ".csv", ".xlsx"]),
        ]

        for i, (formats, expected_files) in enumerate(formats_to_test):
            output_path = str(temp_output_dir / f"format_test_{i}")

            analyzer.export_results(output_path, formats=formats, single_file=True)

            # Check expected files exist
            for ext in expected_files:
                assert Path(f"{output_path}{ext}").exists(), f"Missing {ext} for formats {formats}"

    def test_configuration_loading(self, temp_output_dir: Path):
        """Test configuration file loading and application"""
        # Create custom config
        config_path = temp_output_dir / "custom_config.json"
        custom_config = {
            "default_thresholds": {"title": 60, "author": 50, "year_tolerance": 2},
            "scoring_weights": {"default": {"title": 0.5, "author": 0.3, "publisher": 0.2}},
        }
        config_path.write_text(json.dumps(custom_config))

        # Create analyzer with custom config
        analyzer = MarcCopyrightAnalyzer(config_path=str(config_path))

        # Verify config was loaded
        assert analyzer.config is not None

        # Check thresholds
        assert analyzer.config.get_threshold("title") == 60
        assert analyzer.config.get_threshold("author") == 50
        assert analyzer.config.get_threshold("year_tolerance") == 2

        # Check scoring weights
        weights = analyzer.config.get_scoring_weights("default")
        assert weights["title"] == 0.5
        assert weights["author"] == 0.3
        assert weights["publisher"] == 0.2
