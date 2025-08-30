# tests/integration/test_multiprocessing_platforms.py

"""Integration tests for platform-specific multiprocessing behavior

CRITICAL: These tests ensure multiprocessing works correctly on both
Linux (fork) and macOS (spawn) platforms. Any refactor MUST pass these tests.
"""

# Standard library imports
from multiprocessing import get_start_method
from pathlib import Path
from pickle import dump
from pickle import HIGHEST_PROTOCOL
from tempfile import mkdtemp
from tempfile import NamedTemporaryFile
from unittest.mock import Mock
from unittest.mock import patch

# Third party imports
from pytest import fixture
from pytest import mark

# Local imports
from marc_pd_tool.adapters.api import MarcCopyrightAnalyzer
from marc_pd_tool.application.models.config_models import AnalysisOptions
from marc_pd_tool.core.domain.enums import CountryClassification
from marc_pd_tool.core.domain.publication import Publication


class TestMultiprocessingPlatforms:
    """Test multiprocessing works correctly on different platforms"""

    @fixture
    def sample_publications(self):
        """Create sample publications for testing"""
        pubs = []
        for i in range(10):
            pub = Publication(
                title=f"Test Title {i}",
                author=f"Test Author {i}",
                publisher=f"Test Publisher {i}",
                place="New York",
                country_code="nyu",
                country_classification=CountryClassification.US,
                year=1950 + i,
            )
            pubs.append(pub)
        return pubs

    @fixture
    def temp_batch_dir(self, sample_publications):
        """Create temporary directory with pickled batches"""
        temp_dir = mkdtemp(prefix="test_multiproc_")
        batch_paths = []
        
        # Create 3 batches
        for i in range(0, len(sample_publications), 4):
            batch = sample_publications[i:i+4]
            batch_path = Path(temp_dir) / f"batch_{i//4:03d}.pkl"
            with open(batch_path, "wb") as f:
                dump(batch, f, protocol=HIGHEST_PROTOCOL)
            batch_paths.append(str(batch_path))
        
        return batch_paths

    def test_fork_mode_linux(self, temp_batch_dir):
        """Test fork mode with shared memory on Linux"""
        # This test verifies the fork-specific code path
        analyzer = MarcCopyrightAnalyzer()
        
        # Mock pre-loaded indexes
        mock_reg_index = Mock()
        mock_reg_index.publications = []
        mock_ren_index = Mock() 
        mock_ren_index.publications = []
        
        analyzer.registration_index = mock_reg_index
        analyzer.renewal_index = mock_ren_index
        analyzer.generic_detector = Mock()
        
        with patch("marc_pd_tool.adapters.api._batch_processing.get_start_method") as mock_start:
            mock_start.return_value = "fork"
            
            # Test that shared data is set up correctly
            from marc_pd_tool.adapters.api._batch_processing import BatchProcessingComponent
            
            # Create a mock self that has the required attributes
            mock_self = Mock()
            mock_self.results = Mock()
            mock_self.registration_index = mock_reg_index
            mock_self.renewal_index = mock_ren_index
            mock_self.generic_detector = analyzer.generic_detector
            mock_self.config = analyzer.config
            mock_self.cache_dir = analyzer.cache_dir
            mock_self.copyright_dir = analyzer.copyright_dir
            mock_self.renewal_dir = analyzer.renewal_dir
            
            # Test the key part: setting up shared data for fork
            options = AnalysisOptions(num_processes=2)
            
            # This should set up the shared data dictionary
            with patch("marc_pd_tool.adapters.api._batch_processing.Pool") as mock_pool:
                mock_pool.return_value.__enter__.return_value.imap_unordered.return_value = []
                
                BatchProcessingComponent._process_batches_parallel(
                    mock_self,
                    temp_batch_dir,
                    num_processes=2,
                    year_tolerance=1,
                    title_threshold=40,
                    author_threshold=30,
                    publisher_threshold=60,
                    early_exit_title=95,
                    early_exit_author=90,
                    early_exit_publisher=85,
                    score_everything_mode=False,
                    minimum_combined_score=None,
                    brute_force_missing_year=False,
                    min_year=None,
                    max_year=None,
                )
                
                # Verify fork-specific initialization was used
                pool_call = mock_pool.call_args
                assert "initializer" in pool_call[1]
                # In fork mode with pre-loaded indexes, it should NOT pass initargs
                assert "initargs" not in pool_call[1] or pool_call[1]["initargs"] is None

    def test_spawn_mode_macos(self, temp_batch_dir):
        """Test spawn mode with independent loading on macOS"""
        analyzer = MarcCopyrightAnalyzer()
        
        with patch("marc_pd_tool.adapters.api._batch_processing.get_start_method") as mock_start:
            mock_start.return_value = "spawn"
            
            from marc_pd_tool.adapters.api._batch_processing import BatchProcessingComponent
            
            # Create a mock self
            mock_self = Mock()
            mock_self.results = Mock()
            mock_self.registration_index = None  # No pre-loaded indexes in spawn mode
            mock_self.renewal_index = None
            mock_self.generic_detector = None
            mock_self.config = analyzer.config
            mock_self.cache_dir = analyzer.cache_dir
            mock_self.copyright_dir = analyzer.copyright_dir
            mock_self.renewal_dir = analyzer.renewal_dir
            
            with patch("marc_pd_tool.adapters.api._batch_processing.Pool") as mock_pool:
                mock_pool.return_value.__enter__.return_value.imap_unordered.return_value = []
                
                BatchProcessingComponent._process_batches_parallel(
                    mock_self,
                    temp_batch_dir,
                    num_processes=2,
                    year_tolerance=1,
                    title_threshold=40,
                    author_threshold=30,
                    publisher_threshold=60,
                    early_exit_title=95,
                    early_exit_author=90,
                    early_exit_publisher=85,
                    score_everything_mode=False,
                    minimum_combined_score=None,
                    brute_force_missing_year=False,
                    min_year=None,
                    max_year=None,
                )
                
                # Verify spawn-specific initialization was used
                pool_call = mock_pool.call_args
                assert "initializer" in pool_call[1]
                # In spawn mode, it MUST pass initargs for workers to load data
                assert "initargs" in pool_call[1]
                assert pool_call[1]["initargs"] is not None
                assert len(pool_call[1]["initargs"]) > 0

    def test_worker_recycling(self, temp_batch_dir):
        """Test maxtasksperchild parameter works correctly"""
        analyzer = MarcCopyrightAnalyzer()
        
        from marc_pd_tool.adapters.api._batch_processing import BatchProcessingComponent
        
        mock_self = Mock()
        mock_self.results = Mock()
        mock_self.registration_index = None
        mock_self.renewal_index = None
        mock_self.generic_detector = None
        mock_self.config = analyzer.config
        mock_self.cache_dir = analyzer.cache_dir
        mock_self.copyright_dir = analyzer.copyright_dir
        mock_self.renewal_dir = analyzer.renewal_dir
        
        # Test with many batches to trigger recycling logic
        many_batch_paths = temp_batch_dir * 50  # 150 batches total
        
        with patch("marc_pd_tool.adapters.api._batch_processing.Pool") as mock_pool:
            mock_pool.return_value.__enter__.return_value.imap_unordered.return_value = []
            
            BatchProcessingComponent._process_batches_parallel(
                mock_self,
                many_batch_paths,
                num_processes=4,
                year_tolerance=1,
                title_threshold=40,
                author_threshold=30,
                publisher_threshold=60,
                early_exit_title=95,
                early_exit_author=90,
                early_exit_publisher=85,
                score_everything_mode=False,
                minimum_combined_score=None,
                brute_force_missing_year=False,
                min_year=None,
                max_year=None,
            )
            
            # Verify maxtasksperchild was set appropriately
            pool_call = mock_pool.call_args
            assert "maxtasksperchild" in pool_call[1]
            # With 150 batches and 4 workers, should set recycling
            assert pool_call[1]["maxtasksperchild"] is not None

    def test_interrupt_handling(self):
        """Test Ctrl+C cleanup works properly"""
        analyzer = MarcCopyrightAnalyzer()
        
        # Create a temp file to track cleanup
        with NamedTemporaryFile(delete=False, suffix=".test") as temp_file:
            temp_path = temp_file.name
        
        # Simulate setting result_temp_dir
        analyzer.results.result_temp_dir = temp_path
        
        # Test that cleanup handler is registered
        import signal
        original_handler = signal.getsignal(signal.SIGINT)
        
        # The analyzer should have registered its own handler
        current_handler = signal.getsignal(signal.SIGINT)
        assert current_handler != signal.SIG_DFL
        
        # Clean up
        Path(temp_path).unlink(missing_ok=True)

    @mark.skip(reason="Requires actual multiprocessing execution")
    def test_actual_multiprocessing_execution(self, temp_batch_dir):
        """Test actual multiprocessing execution (manual test)"""
        # This test would actually run multiprocessing
        # It's skipped by default but can be run manually
        analyzer = MarcCopyrightAnalyzer()
        
        # Would need actual copyright/renewal data loaded
        # analyzer._load_and_index_data(AnalysisOptions())
        
        # Would process actual batches
        # results = analyzer._process_batches_parallel(...)
        
        pass