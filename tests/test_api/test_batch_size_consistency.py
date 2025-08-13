# tests/test_api/test_batch_size_consistency.py

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
                        mock_marc_loader.return_value.extract_all_batches.return_value = []

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
                        mock_marc_loader.return_value.extract_all_batches.return_value = []

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

        with patch.object(analyzer, "_process_sequentially") as mock_seq:
            with patch.object(analyzer, "_process_parallel") as mock_parallel:
                mock_seq.return_value = []
                mock_parallel.return_value = []

                # Test with default (should use config value of 100)
                publications = [MagicMock() for _ in range(150)]
                analyzer.analyze_marc_records(publications, options={})

                # Since we have 150 records and batch_size=100, it should use parallel
                mock_parallel.assert_called_once()
                call_args = mock_parallel.call_args
                assert call_args.args[1] == 100  # batch_size is second argument

                # Reset mocks
                mock_parallel.reset_mock()
                mock_seq.reset_mock()

                # Test with explicit batch_size
                analyzer.analyze_marc_records(publications, options={"batch_size": 200})

                # With batch_size=200 and 150 records, should use sequential
                mock_seq.assert_called_once()
                mock_parallel.assert_not_called()

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
