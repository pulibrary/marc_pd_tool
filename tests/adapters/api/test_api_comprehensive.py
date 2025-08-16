# tests/adapters/api/test_api_comprehensive.py

"""
Comprehensive tests for API module - cleaned version with unnecessary skipped tests removed
"""

# Standard library imports
from pathlib import Path

# Local imports
from marc_pd_tool.adapters.api import AnalysisResults
from marc_pd_tool.adapters.api import MarcCopyrightAnalyzer
from marc_pd_tool.core.domain.publication import Publication


class TestAnalysisResultsMissingCoverage:
    """Test missing coverage areas in AnalysisResults"""

    def test_update_statistics_no_country_classification(self):
        """Test _update_statistics with publication missing country classification"""
        results = AnalysisResults()

        # Create publication without country classification
        pub = Publication(title="Test", author="Author")
        pub.copyright_status = "US_PUBLIC_DOMAIN"

        # Should handle missing country classification
        results.add_publication(pub)

        # Should increment counters appropriately
        assert results.statistics.total_records == 1
        assert results.statistics.get("unknown_country", 0) == 1

    def test_load_all_publications_with_errors(self, tmp_path):
        """Test load_all_publications with file errors"""
        results = AnalysisResults()

        # Add non-existent file paths
        results.result_file_paths = [
            str(tmp_path / "nonexistent1.pkl"),
            str(tmp_path / "nonexistent2.pkl"),
        ]

        # Should handle errors gracefully
        results.load_all_publications()

        # Should have empty publications list
        assert len(results.publications) == 0

    def test_load_all_publications_empty(self):
        """Test load_all_publications with no files"""
        results = AnalysisResults()

        # No files to load
        results.result_file_paths = []

        # Should handle empty list
        results.load_all_publications()

        assert len(results.publications) == 0


class TestMarcCopyrightAnalyzerMissingCoverage:
    """Test missing coverage areas in MarcCopyrightAnalyzer"""

    def test_export_results_all_formats(self, tmp_path):
        """Test export_results with all formats"""
        analyzer = MarcCopyrightAnalyzer()

        # Add test publication
        pub = Publication(title="Test", author="Author")
        pub.copyright_status = "US_PUBLIC_DOMAIN"
        analyzer.results.add_publication(pub)

        # Export in all formats
        output_path = str(tmp_path / "output")
        analyzer.export_results(
            output_path, formats=["json", "csv", "xlsx", "html"], single_file=True
        )

        # Check files were created
        assert Path(f"{output_path}.json").exists()
        # Note: Other formats depend on JSON being created first

    def test_get_results(self):
        """Test get_results method"""
        analyzer = MarcCopyrightAnalyzer()

        # Add some test data
        pub = Publication(title="Test", author="Author")
        analyzer.results.add_publication(pub)

        # Get results
        results = analyzer.get_results()

        # Should return the same results object
        assert results is analyzer.results
        assert len(results.publications) == 1


# Note: Removed the following skipped tests as they test internal implementation details
# that are not meaningful to test with mocks:
# - test_linux_fork_mode_processing: Tests Linux-specific fork mode, but just mocks everything
# - test_ground_truth_analysis_comprehensive: Tests with incorrect dataclass structure
# - test_batch_pickle_saving: Tests non-existent internal method
# - test_pool_worker_error_recovery: Tests internal pool error handling with mocks
# - test_memory_cleanup_on_large_datasets: Tests memory cleanup with mocks

# These tests were providing no real value as they were either:
# 1. Testing methods that don't exist
# 2. Testing with incorrect data structures
# 3. Mocking so heavily that they weren't testing actual behavior
