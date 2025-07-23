# tests/test_infrastructure/test_year_filtered_caching.py

"""Tests for year-filtered caching functionality"""

# Standard library imports
from os.path import exists
from os.path import join
import shutil
import tempfile
import unittest
from unittest.mock import patch

# Local imports
from marc_pd_tool.data.publication import Publication
from marc_pd_tool.infrastructure.cache_manager import CacheManager


class TestYearFilteredCaching(unittest.TestCase):
    """Test the year-filtered caching functionality"""

    def setUp(self):
        """Set up test fixtures"""
        self.test_dir = tempfile.mkdtemp()
        self.cache_dir = join(self.test_dir, "cache")
        self.cache_manager = CacheManager(self.cache_dir)

        # Create mock publications with different years
        self.pubs_1950s = [
            self._create_publication("Book 1", 1950),
            self._create_publication("Book 2", 1955),
            self._create_publication("Book 3", 1959),
        ]

        self.pubs_1960s = [
            self._create_publication("Book 4", 1960),
            self._create_publication("Book 5", 1965),
            self._create_publication("Book 6", 1969),
        ]

        self.all_pubs = self.pubs_1950s + self.pubs_1960s

    def tearDown(self):
        """Clean up test directory"""
        if exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def _create_publication(self, title: str, year: int) -> Publication:
        """Create a mock publication"""
        pub = Publication(title=title, pub_date=str(year), source="test")
        pub.year = year
        return pub

    def test_cache_filename_generation(self):
        """Test that cache filenames are generated correctly for different year ranges"""
        # Test all years
        filename = self.cache_manager._get_year_range_cache_filename(
            "publications", None, None, False
        )
        self.assertEqual(filename, "publications_all.pkl")

        # Test brute force mode
        filename = self.cache_manager._get_year_range_cache_filename(
            "publications", 1950, 1960, True
        )
        self.assertEqual(filename, "publications_all.pkl")

        # Test specific year range
        filename = self.cache_manager._get_year_range_cache_filename(
            "publications", 1950, 1960, False
        )
        self.assertEqual(filename, "publications_1950_1960.pkl")

        # Test min year only
        filename = self.cache_manager._get_year_range_cache_filename(
            "publications", 1950, None, False
        )
        self.assertEqual(filename, "publications_1950_present.pkl")

        # Test max year only
        filename = self.cache_manager._get_year_range_cache_filename(
            "publications", None, 1960, False
        )
        self.assertEqual(filename, "publications_earliest_1960.pkl")

    def test_copyright_cache_with_year_range(self):
        """Test caching and retrieving copyright data with year ranges"""
        copyright_dir = "/test/copyright"

        # Cache data for 1950-1960
        success = self.cache_manager.cache_copyright_data(
            copyright_dir, self.pubs_1950s, 1950, 1960, False
        )
        self.assertTrue(success)

        # Verify cache directory structure
        expected_cache_dir = join(self.cache_dir, "copyright_data", "1950_1960")
        self.assertTrue(exists(expected_cache_dir))

        # Try to retrieve with same year range - should succeed
        with patch.object(self.cache_manager, "_is_cache_valid", return_value=True):
            with patch.object(self.cache_manager, "_load_cache_data", return_value=self.pubs_1950s):
                cached_data = self.cache_manager.get_cached_copyright_data(
                    copyright_dir, 1950, 1960, False
                )
                self.assertIsNotNone(cached_data)
                self.assertEqual(len(cached_data), 3)

        # Try to retrieve with different year range - should return None
        cached_data = self.cache_manager.get_cached_copyright_data(copyright_dir, 1960, 1970, False)
        self.assertIsNone(cached_data)

    def test_renewal_cache_with_year_range(self):
        """Test caching and retrieving renewal data with year ranges"""
        renewal_dir = "/test/renewal"

        # Cache data for all years
        success = self.cache_manager.cache_renewal_data(
            renewal_dir, self.all_pubs, None, None, False
        )
        self.assertTrue(success)

        # Verify cache directory structure for all years
        expected_cache_dir = join(self.cache_dir, "renewal_data", "all")
        self.assertTrue(exists(expected_cache_dir))

    def test_brute_force_mode_caching(self):
        """Test that brute force mode uses 'all' cache regardless of year filters"""
        copyright_dir = "/test/copyright"

        # Cache with brute force mode even though years are specified
        success = self.cache_manager.cache_copyright_data(
            copyright_dir, self.all_pubs, 1950, 1960, True  # brute_force=True
        )
        self.assertTrue(success)

        # Should create 'all' cache directory, not year-specific
        expected_cache_dir = join(self.cache_dir, "copyright_data", "all")
        self.assertTrue(exists(expected_cache_dir))

        # Should not create year-specific directory
        unexpected_cache_dir = join(self.cache_dir, "copyright_data", "1950_1960")
        self.assertFalse(exists(unexpected_cache_dir))

    @patch("marc_pd_tool.infrastructure.cache_manager.logger")
    def test_cache_logging(self, mock_logger):
        """Test that appropriate log messages are generated"""
        copyright_dir = "/test/copyright"

        # Cache with specific year range
        self.cache_manager.cache_copyright_data(copyright_dir, self.pubs_1950s, 1950, 1960, False)

        # Check for year-specific log message
        mock_logger.info.assert_any_call(
            "Caching copyright data for years 1950-1960 (3 publications)..."
        )

        # Cache for all years
        self.cache_manager.cache_copyright_data(copyright_dir, self.all_pubs, None, None, False)

        # Check for all-years log message
        mock_logger.info.assert_any_call("Caching copyright data for ALL years (6 publications)...")

    def test_multiple_year_range_caches_coexist(self):
        """Test that multiple caches for different year ranges can coexist"""
        copyright_dir = "/test/copyright"

        # Cache different year ranges
        self.cache_manager.cache_copyright_data(copyright_dir, self.pubs_1950s, 1950, 1959, False)
        self.cache_manager.cache_copyright_data(copyright_dir, self.pubs_1960s, 1960, 1969, False)
        self.cache_manager.cache_copyright_data(copyright_dir, self.all_pubs, None, None, False)

        # Verify all cache directories exist
        cache_dirs = [
            join(self.cache_dir, "copyright_data", "1950_1959"),
            join(self.cache_dir, "copyright_data", "1960_1969"),
            join(self.cache_dir, "copyright_data", "all"),
        ]

        for cache_dir in cache_dirs:
            self.assertTrue(exists(cache_dir), f"Cache directory {cache_dir} should exist")


if __name__ == "__main__":
    unittest.main()
