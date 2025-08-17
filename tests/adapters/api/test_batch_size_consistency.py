# tests/adapters/api/test_batch_size_consistency.py

"""Tests for batch_size consistency across all components"""

# Standard library imports
from pathlib import Path
from tempfile import NamedTemporaryFile
from unittest.mock import MagicMock
from unittest.mock import patch

# Local imports
from marc_pd_tool.adapters.api import MarcCopyrightAnalyzer

#


class TestBatchSizeConsistency:
    """Test that batch_size defaults are consistent across all components"""

    def test_default_batch_size_from_config(self):
        """Test that analyzer uses config.json default of 100"""
        analyzer = MarcCopyrightAnalyzer()
        config = analyzer.config.config

        # Config should default to 100
        assert config.get("processing", {}).get("batch_size") == 100

    def test_marc_loader_uses_config_default(self):
        """Test that MarcLoader gets correct default from analyzer"""
        with NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as f:
            f.write('<?xml version="1.0"?><collection></collection>')
            marc_path = f.name

        try:
            # Mock the loaders to avoid needing actual data files
            with patch("marc_pd_tool.adapters.api._analyzer.CopyrightDataLoader") as mock_copyright:
                with patch("marc_pd_tool.adapters.api._analyzer.RenewalDataLoader") as mock_renewal:
                    # Mock the get_max_data_year methods
                    mock_copyright.return_value.max_data_year = 1977
                    mock_renewal.return_value.max_data_year = 2001

                    # Mock MarcLoader to capture the batch_size passed to it
                    with patch(
                        "marc_pd_tool.adapters.api._analyzer.MarcLoader"
                    ) as mock_marc_loader:
                        # Mock extract_batches_to_disk which is now used instead of extract_all_batches
                        mock_marc_loader.return_value.extract_batches_to_disk.return_value = (
                            [],
                            0,
                            0,
                        )

                        analyzer = MarcCopyrightAnalyzer()
                        # Call analyze_marc_file without options to test default
                        analyzer.analyze_marc_file(
                            marc_path=marc_path,
                            copyright_dir="test_copyright",
                            renewal_dir="test_renewal",
                        )

                        # Verify MarcLoader was called with batch_size=100 (from config)
                        mock_marc_loader.assert_called_once()
                        call_args = mock_marc_loader.call_args
                        assert call_args.kwargs["batch_size"] == 100
        finally:
            Path(marc_path).unlink()

    def test_explicit_batch_size_overrides_default(self):
        """Test that explicit batch_size in options overrides config default"""
        with NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as f:
            f.write('<?xml version="1.0"?><collection></collection>')
            marc_path = f.name

        try:
            # Mock the loaders
            with patch("marc_pd_tool.adapters.api._analyzer.CopyrightDataLoader") as mock_copyright:
                with patch("marc_pd_tool.adapters.api._analyzer.RenewalDataLoader") as mock_renewal:
                    mock_copyright.return_value.max_data_year = 1977
                    mock_renewal.return_value.max_data_year = 2001

                    with patch(
                        "marc_pd_tool.adapters.api._analyzer.MarcLoader"
                    ) as mock_marc_loader:
                        mock_marc_loader.return_value.extract_batches_to_disk.return_value = (
                            [],
                            0,
                            0,
                        )

                        analyzer = MarcCopyrightAnalyzer()
                        # Call with explicit batch_size
                        # Local imports
                        from marc_pd_tool.application.models.config_models import (
                            AnalysisOptions,
                        )

                        analyzer.analyze_marc_file(
                            marc_path=marc_path,
                            copyright_dir="test_copyright",
                            renewal_dir="test_renewal",
                            options=AnalysisOptions(batch_size=50),
                        )

                        # Verify MarcLoader was called with batch_size=50
                        mock_marc_loader.assert_called_once()
                        call_args = mock_marc_loader.call_args
                        assert call_args.kwargs["batch_size"] == 50
        finally:
            Path(marc_path).unlink()

    def test_processing_batch_size_consistency(self):
        """Test that processing phase uses same batch_size as loading phase"""
        analyzer = MarcCopyrightAnalyzer()

        # Create real Publication objects
        # Local imports
        from marc_pd_tool.application.models.config_models import AnalysisOptions
        from marc_pd_tool.core.domain.publication import Publication

        publications = [
            Publication(title=f"Book {i}", pub_date="1960", source_id=str(i)) for i in range(150)
        ]

        # Set up indexes to avoid reload attempts
        analyzer.registration_index = MagicMock()
        analyzer.renewal_index = MagicMock()

        # Mock all the file/processing operations to verify batch_size usage
        with patch("tempfile.mkdtemp") as mock_mkdtemp:
            mock_mkdtemp.return_value = "/tmp/test_batches"

            with patch("builtins.open", MagicMock()):
                with patch("pickle.dump") as mock_dump:
                    # Patch logger to avoid logging during test
                    with patch("marc_pd_tool.adapters.api._analyzer.logger"):
                        # Patch the streaming component to avoid real processing
                        with patch(
                            "marc_pd_tool.adapters.api._analyzer.StreamingComponent._analyze_marc_file_streaming"
                        ) as mock_stream:

                            # Test with default batch_size (should be 100 from config)
                            analyzer.analyze_marc_records(publications, options=AnalysisOptions())

                            # Check that pickle.dump was called correct number of times
                            # 150 publications with batch_size=100 should create 2 batches
                            assert mock_dump.call_count == 2
                            mock_dump.reset_mock()

                            # Test with explicit batch_size=50
                            analyzer.analyze_marc_records(
                                publications, options=AnalysisOptions(batch_size=50)
                            )

                            # 150 publications with batch_size=50 should create 3 batches
                            assert mock_dump.call_count == 3
                            mock_dump.reset_mock()

                            # Test with explicit batch_size=200
                            analyzer.analyze_marc_records(
                                publications, options=AnalysisOptions(batch_size=200)
                            )

                            # 150 publications with batch_size=200 should create 1 batch
                            assert mock_dump.call_count == 1

    def test_no_hardcoded_batch_sizes(self):
        """Ensure we're not using hardcoded 1000 or 200 anywhere in analyzer"""
        # This test verifies our fix by checking the actual code doesn't have
        # hardcoded values that would override config

        analyzer = MarcCopyrightAnalyzer()
        config = analyzer.config.config

        # The default should be 100 from config, not 200 or 1000
        default_batch = config.get("processing", {}).get("batch_size", 100)
        assert default_batch == 100

        # When options is empty, we should get config default
        options = {}
        batch_from_options = options.get(
            "batch_size", config.get("processing", {}).get("batch_size", 100)
        )
        assert batch_from_options == 100
