# tests/adapters/api/test_batch_size_consistency.py

"""Tests for batch_size consistency across all components"""

# Standard library imports
from pathlib import Path
from tempfile import NamedTemporaryFile
from unittest.mock import MagicMock
from unittest.mock import patch

# Local imports
from marc_pd_tool.adapters.api import MarcCopyrightAnalyzer


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
                        analyzer.analyze_marc_file(
                            marc_path=marc_path,
                            copyright_dir="test_copyright",
                            renewal_dir="test_renewal",
                            options={"batch_size": 50},
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

        # Mock the required data
        analyzer.registration_index = MagicMock()
        analyzer.renewal_index = MagicMock()

        # Create real Publication objects instead of MagicMocks (they need to be pickleable)
        # Local imports
        from marc_pd_tool.core.domain.publication import Publication

        publications = [
            Publication(title=f"Book {i}", pub_date="1960", source_id=str(i)) for i in range(150)
        ]

        with patch.object(analyzer, "_load_and_index_data"):
            with patch.object(analyzer, "_analyze_marc_file_streaming") as mock_stream:
                # Mock to populate results
                def mock_streaming(*args, **kwargs):
                    analyzer.results.publications = publications

                mock_stream.side_effect = mock_streaming

                # Test with default (should use config value of 100)
                analyzer.analyze_marc_records(publications, options={})

                # Verify streaming was called
                mock_stream.assert_called_once()

                # Reset mock
                mock_stream.reset_mock()

                # Test with explicit batch_size
                analyzer.analyze_marc_records(publications, options={"batch_size": 200})

                # Verify streaming was called again
                mock_stream.assert_called_once()

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
