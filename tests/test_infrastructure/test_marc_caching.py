# tests/test_infrastructure/test_marc_caching.py

"""Tests for MARC data caching functionality"""

# Standard library imports
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

# Local imports
from marc_pd_tool.core.domain.publication import Publication
from marc_pd_tool.infrastructure import CacheManager


class TestMarcCaching(TestCase):
    """Test MARC data caching functionality"""

    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        self.cache_manager = CacheManager(str(self.temp_path / "test_cache"))

    def tearDown(self):
        """Clean up test fixtures"""
        self.temp_dir.cleanup()

    def test_marc_cache_directories_created(self):
        """Test that MARC cache directory is created"""
        self.assertTrue(Path(self.cache_manager.marc_cache_dir).exists())

    def test_marc_cache_miss(self):
        """Test MARC cache miss scenario"""
        marc_path = "/test/path/marc.xml"
        year_ranges = {
            "copyright_min": 1923,
            "copyright_max": 1977,
            "renewal_min": 1950,
            "renewal_max": 1991,
        }
        filtering_options = {
            "min_year": 1929,
            "max_year": 1970,
            "us_only": False,
            "batch_size": 200,
        }

        # Should return None for cache miss
        result = self.cache_manager.get_cached_marc_data(marc_path, year_ranges, filtering_options)
        self.assertIsNone(result)

    def test_marc_cache_hit_after_save(self):
        """Test MARC cache hit after saving data"""
        # Create a real test file for path validation
        test_marc_file = self.temp_path / "test_marc.xml"
        test_marc_file.write_text("<collection></collection>")
        marc_path = str(test_marc_file)
        year_ranges = {
            "copyright_min": 1923,
            "copyright_max": 1977,
            "renewal_min": 1950,
            "renewal_max": 1991,
        }
        filtering_options = {
            "min_year": 1929,
            "max_year": 1970,
            "us_only": False,
            "batch_size": 200,
        }

        # Create test MARC batches
        test_batches = [
            [
                Publication(
                    title="Test Book 1",
                    author="Test Author 1",
                    pub_date="1945",
                    publisher="Test Publisher",
                    source="MARC",
                ),
                Publication(
                    title="Test Book 2",
                    author="Test Author 2",
                    pub_date="1950",
                    publisher="Test Publisher 2",
                    source="MARC",
                ),
            ],
            [
                Publication(
                    title="Test Book 3",
                    author="Test Author 3",
                    pub_date="1960",
                    publisher="Test Publisher 3",
                    source="MARC",
                )
            ],
        ]

        # Cache the data
        success = self.cache_manager.cache_marc_data(
            marc_path, year_ranges, filtering_options, test_batches
        )
        self.assertTrue(success)

        # Retrieve from cache
        cached_batches = self.cache_manager.get_cached_marc_data(
            marc_path, year_ranges, filtering_options
        )
        self.assertIsNotNone(cached_batches)
        self.assertEqual(len(cached_batches), 2)
        self.assertEqual(len(cached_batches[0]), 2)
        self.assertEqual(len(cached_batches[1]), 1)
        self.assertEqual(cached_batches[0][0].original_title, "Test Book 1")

    def test_marc_cache_invalidation_year_ranges(self):
        """Test that cache is invalidated when year ranges change"""
        # Create a real test file for path validation
        test_marc_file = self.temp_path / "test_marc.xml"
        test_marc_file.write_text("<collection></collection>")
        marc_path = str(test_marc_file)
        year_ranges_1 = {
            "copyright_min": 1923,
            "copyright_max": 1977,
            "renewal_min": 1950,
            "renewal_max": 1991,
        }
        year_ranges_2 = {
            "copyright_min": 1923,
            "copyright_max": 1980,  # Changed max year
            "renewal_min": 1950,
            "renewal_max": 1991,
        }
        filtering_options = {
            "min_year": 1929,
            "max_year": 1970,
            "us_only": False,
            "batch_size": 200,
        }

        # Create and cache test data
        test_batches = [[Publication(title="Test", author="Author", source="MARC")]]

        success = self.cache_manager.cache_marc_data(
            marc_path, year_ranges_1, filtering_options, test_batches
        )
        self.assertTrue(success)

        # Should get cache hit with same year ranges
        cached = self.cache_manager.get_cached_marc_data(
            marc_path, year_ranges_1, filtering_options
        )
        self.assertIsNotNone(cached)

        # Should get cache miss with different year ranges
        cached = self.cache_manager.get_cached_marc_data(
            marc_path, year_ranges_2, filtering_options
        )
        self.assertIsNone(cached)

    def test_marc_cache_invalidation_filtering_options(self):
        """Test that cache is invalidated when filtering options change"""
        # Create a real test file for path validation
        test_marc_file = self.temp_path / "test_marc.xml"
        test_marc_file.write_text("<collection></collection>")
        marc_path = str(test_marc_file)
        year_ranges = {
            "copyright_min": 1923,
            "copyright_max": 1977,
            "renewal_min": 1950,
            "renewal_max": 1991,
        }
        filtering_options_1 = {
            "min_year": 1929,
            "max_year": 1970,
            "us_only": False,
            "batch_size": 200,
        }
        filtering_options_2 = {
            "min_year": 1929,
            "max_year": 1970,
            "us_only": True,  # Changed us_only flag
            "batch_size": 200,
        }

        # Create and cache test data
        test_batches = [[Publication(title="Test", author="Author", source="MARC")]]

        success = self.cache_manager.cache_marc_data(
            marc_path, year_ranges, filtering_options_1, test_batches
        )
        self.assertTrue(success)

        # Should get cache hit with same filtering options
        cached = self.cache_manager.get_cached_marc_data(
            marc_path, year_ranges, filtering_options_1
        )
        self.assertIsNotNone(cached)

        # Should get cache miss with different filtering options
        cached = self.cache_manager.get_cached_marc_data(
            marc_path, year_ranges, filtering_options_2
        )
        self.assertIsNone(cached)

    def test_marc_cache_info_includes_marc_data(self):
        """Test that cache info includes MARC data component"""
        cache_info = self.cache_manager.get_cache_info()

        self.assertIn("components", cache_info)
        self.assertIn("marc_data", cache_info["components"])

        # Initially should be not cached
        self.assertFalse(cache_info["components"]["marc_data"]["cached"])

        # After caching data, should be cached
        test_marc_file = self.temp_path / "test_marc.xml"
        test_marc_file.write_text("<collection></collection>")
        marc_path = str(test_marc_file)
        year_ranges = {"copyright_min": 1923, "copyright_max": 1977}
        filtering_options = {"min_year": 1929, "us_only": False}
        test_batches = [[Publication(title="Test", author="Author", source="MARC")]]

        self.cache_manager.cache_marc_data(marc_path, year_ranges, filtering_options, test_batches)

        cache_info = self.cache_manager.get_cache_info()
        self.assertTrue(cache_info["components"]["marc_data"]["cached"])

    def test_marc_cache_clear_all_caches(self):
        """Test that clear_all_caches removes MARC cache"""
        # Cache some data
        test_marc_file = self.temp_path / "test_marc.xml"
        test_marc_file.write_text("<collection></collection>")
        marc_path = str(test_marc_file)
        year_ranges = {"copyright_min": 1923, "copyright_max": 1977}
        filtering_options = {"min_year": 1929, "us_only": False}
        test_batches = [[Publication(title="Test", author="Author", source="MARC")]]

        self.cache_manager.cache_marc_data(marc_path, year_ranges, filtering_options, test_batches)

        # Verify it's cached
        cached = self.cache_manager.get_cached_marc_data(marc_path, year_ranges, filtering_options)
        self.assertIsNotNone(cached)

        # Clear all caches
        self.cache_manager.clear_all_caches()

        # Verify it's no longer cached
        cached = self.cache_manager.get_cached_marc_data(marc_path, year_ranges, filtering_options)
        self.assertIsNone(cached)

    def test_marc_cache_empty_batches(self):
        """Test caching empty MARC batches"""
        test_marc_file = self.temp_path / "test_marc.xml"
        test_marc_file.write_text("<collection></collection>")
        marc_path = str(test_marc_file)
        year_ranges = {"copyright_min": 1923, "copyright_max": 1977}
        filtering_options = {"min_year": 1929, "us_only": False}
        empty_batches = []

        success = self.cache_manager.cache_marc_data(
            marc_path, year_ranges, filtering_options, empty_batches
        )
        self.assertTrue(success)

        cached_batches = self.cache_manager.get_cached_marc_data(
            marc_path, year_ranges, filtering_options
        )
        self.assertIsNotNone(cached_batches)
        self.assertEqual(len(cached_batches), 0)
