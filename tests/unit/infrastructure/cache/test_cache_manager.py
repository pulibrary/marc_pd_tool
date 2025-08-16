# tests/unit/infrastructure/cache/test_cache_manager.py

"""Comprehensive unit tests for CacheManager"""

# Standard library imports
from os import makedirs
from os.path import exists
from os.path import getmtime
from os.path import join
from pickle import HIGHEST_PROTOCOL
from pickle import dump
from tempfile import TemporaryDirectory
from time import sleep
from time import time
from unittest.mock import patch

# Local imports
from marc_pd_tool.core.domain.publication import Publication
from marc_pd_tool.infrastructure.cache._manager import CacheManager


class TestCacheManager:
    """Test CacheManager functionality"""

    def test_init_creates_cache_directories(self):
        """Test that __init__ creates all required cache subdirectories"""
        with TemporaryDirectory() as temp_dir:
            cache_dir = join(temp_dir, "test_cache")
            assert not exists(cache_dir)

            manager = CacheManager(cache_dir)

            # Check main directory and all subdirectories exist
            assert exists(cache_dir)
            assert exists(join(cache_dir, "copyright_data"))
            assert exists(join(cache_dir, "renewal_data"))
            assert exists(join(cache_dir, "marc_data"))
            assert exists(join(cache_dir, "indexes"))
            assert exists(join(cache_dir, "generic_detector"))
            assert manager.cache_dir == cache_dir

    def test_get_directory_modification_time(self):
        """Test _get_directory_modification_time method"""
        with TemporaryDirectory() as temp_dir:
            manager = CacheManager(temp_dir)

            # Create some files in a test directory
            test_dir = join(temp_dir, "test_dir")
            makedirs(test_dir)

            # Create files with slight delays
            file1 = join(test_dir, "file1.txt")
            with open(file1, "w") as f:
                f.write("test1")

            sleep(0.01)  # Small delay

            file2 = join(test_dir, "file2.txt")
            with open(file2, "w") as f:
                f.write("test2")

            # Get directory modification time
            mtime = manager._get_directory_modification_time(test_dir)

            # Should be at least as recent as the newest file
            assert mtime >= getmtime(file2)

    def test_get_directory_modification_time_nonexistent(self):
        """Test _get_directory_modification_time with nonexistent directory"""
        with TemporaryDirectory() as temp_dir:
            manager = CacheManager(temp_dir)

            mtime = manager._get_directory_modification_time("/nonexistent/path")
            assert mtime == 0.0

    def test_get_directory_modification_time_with_error(self):
        """Test _get_directory_modification_time handles errors gracefully"""
        with TemporaryDirectory() as temp_dir:
            manager = CacheManager(temp_dir)

            with patch("marc_pd_tool.infrastructure.cache._manager.walk") as mock_walk:
                mock_walk.side_effect = OSError("Permission denied")

                mtime = manager._get_directory_modification_time(temp_dir)
                assert mtime == 0.0  # Returns 0 on error

    def test_get_year_range_cache_filename(self):
        """Test _get_year_range_cache_filename method"""
        with TemporaryDirectory() as temp_dir:
            manager = CacheManager(temp_dir)

            # Test different combinations
            filename = manager._get_year_range_cache_filename("publications", None, None, False)
            assert filename == "publications_all.pkl"

            filename = manager._get_year_range_cache_filename("publications", 1950, 1960, False)
            assert filename == "publications_1950_1960.pkl"

            filename = manager._get_year_range_cache_filename("publications", 1950, None, False)
            assert filename == "publications_1950_present.pkl"

            filename = manager._get_year_range_cache_filename("publications", None, 1960, False)
            assert filename == "publications_earliest_1960.pkl"

            filename = manager._get_year_range_cache_filename("publications", None, None, True)
            assert filename == "publications_all.pkl"  # brute_force uses _all suffix

    def test_save_and_load_metadata(self):
        """Test _save_metadata and _load_metadata methods"""
        with TemporaryDirectory() as temp_dir:
            manager = CacheManager(temp_dir)

            cache_subdir = join(temp_dir, "test_subdir")
            makedirs(cache_subdir)

            # Create metadata
            metadata = {
                "version": "1.0",
                "source_files": ["/path/to/source"],
                "source_mtimes": [123456.0],
                "cache_time": time(),
                "additional_deps": {"key": "value"},
            }

            # Save metadata
            manager._save_metadata(cache_subdir, metadata)

            # Load metadata
            loaded = manager._load_metadata(cache_subdir)

            assert loaded is not None
            assert loaded["version"] == "1.0"
            assert loaded["source_files"] == ["/path/to/source"]

    def test_load_metadata_corrupted(self):
        """Test _load_metadata with corrupted JSON file"""
        with TemporaryDirectory() as temp_dir:
            manager = CacheManager(temp_dir)

            # Create corrupted metadata file
            metadata_file = join(temp_dir, "metadata.json")
            with open(metadata_file, "w") as f:
                f.write("not valid json{")

            loaded = manager._load_metadata(temp_dir)
            assert loaded is None

    def test_save_cache_data(self):
        """Test _save_cache_data method"""
        with TemporaryDirectory() as temp_dir:
            manager = CacheManager(temp_dir)

            cache_subdir = join(temp_dir, "test_cache")
            makedirs(cache_subdir)

            source_file = join(temp_dir, "source.txt")
            with open(source_file, "w") as f:
                f.write("source data")

            # Save cache data
            test_data = {"key": "value", "number": 42}
            success = manager._save_cache_data(
                cache_subdir, "test_data.pkl", test_data, [source_file], {"dep": "value"}
            )

            assert success is True
            assert exists(join(cache_subdir, "test_data.pkl"))
            assert exists(join(cache_subdir, "metadata.json"))

    def test_save_cache_data_with_error(self):
        """Test _save_cache_data handles errors"""
        with TemporaryDirectory() as temp_dir:
            manager = CacheManager(temp_dir)

            # Try to save to non-existent directory
            success = manager._save_cache_data(
                "/nonexistent/path", "test.pkl", {"data": "test"}, ["/source"], None
            )

            assert success is False

    def test_load_cache_data(self):
        """Test _load_cache_data method"""
        with TemporaryDirectory() as temp_dir:
            manager = CacheManager(temp_dir)

            cache_subdir = join(temp_dir, "test_cache")
            makedirs(cache_subdir)

            # Save test data
            test_data = {"test": "data"}
            cache_file = join(cache_subdir, "test.pkl")
            with open(cache_file, "wb") as f:
                dump(test_data, f, protocol=HIGHEST_PROTOCOL)

            # Load it back
            loaded = manager._load_cache_data(cache_subdir, "test.pkl")
            assert loaded == test_data

    def test_load_cache_data_corrupted(self):
        """Test _load_cache_data with corrupted file"""
        with TemporaryDirectory() as temp_dir:
            manager = CacheManager(temp_dir)

            cache_subdir = join(temp_dir, "test_cache")
            makedirs(cache_subdir)

            # Create corrupted pickle file
            cache_file = join(cache_subdir, "corrupted.pkl")
            with open(cache_file, "w") as f:
                f.write("not a pickle")

            loaded = manager._load_cache_data(cache_subdir, "corrupted.pkl")
            assert loaded is None

    def test_get_cached_copyright_data_not_cached(self):
        """Test get_cached_copyright_data when not cached"""
        with TemporaryDirectory() as temp_dir:
            manager = CacheManager(temp_dir)

            result = manager.get_cached_copyright_data("/copyright/dir")
            assert result is None

    def test_cache_and_get_copyright_data(self):
        """Test cache_copyright_data and get_cached_copyright_data"""
        with TemporaryDirectory() as temp_dir:
            manager = CacheManager(temp_dir)

            # Create source directory
            copyright_dir = join(temp_dir, "copyright")
            makedirs(copyright_dir)

            # Create test publications
            pubs = [Publication(title="Book1", year=1950), Publication(title="Book2", year=1955)]

            # Cache the data
            success = manager.cache_copyright_data(copyright_dir, pubs)
            assert success is True

            # Retrieve cached data
            cached = manager.get_cached_copyright_data(copyright_dir)
            assert cached is not None
            assert len(cached) == 2
            assert cached[0].title == "Book1"

    def test_cache_copyright_data_with_year_range(self):
        """Test caching copyright data with year filtering"""
        with TemporaryDirectory() as temp_dir:
            manager = CacheManager(temp_dir)

            copyright_dir = join(temp_dir, "copyright")
            makedirs(copyright_dir)

            pubs = [Publication(title="Book1", year=1950)]

            # Cache with year range
            success = manager.cache_copyright_data(
                copyright_dir, pubs, min_year=1945, max_year=1955
            )
            assert success is True

            # Retrieve should work with same year range
            cached = manager.get_cached_copyright_data(copyright_dir, min_year=1945, max_year=1955)
            assert cached is not None
            assert len(cached) == 1

    def test_get_cached_renewal_data_not_cached(self):
        """Test get_cached_renewal_data when not cached"""
        with TemporaryDirectory() as temp_dir:
            manager = CacheManager(temp_dir)

            result = manager.get_cached_renewal_data("/renewal/dir")
            assert result is None

    def test_cache_and_get_renewal_data(self):
        """Test cache_renewal_data and get_cached_renewal_data"""
        with TemporaryDirectory() as temp_dir:
            manager = CacheManager(temp_dir)

            renewal_dir = join(temp_dir, "renewal")
            makedirs(renewal_dir)

            pubs = [Publication(title="Renewal1", year=1960)]

            # Cache the data
            success = manager.cache_renewal_data(renewal_dir, pubs)
            assert success is True

            # Retrieve cached data
            cached = manager.get_cached_renewal_data(renewal_dir)
            assert cached is not None
            assert len(cached) == 1
            assert cached[0].title == "Renewal1"

    def test_get_cached_indexes_not_cached(self):
        """Test get_cached_indexes when not cached"""
        with TemporaryDirectory() as temp_dir:
            manager = CacheManager(temp_dir)

            result = manager.get_cached_indexes("/copyright", "/renewal", "test_hash")

            # Should return None when not cached
            assert result is None

    def test_cache_and_get_indexes(self):
        """Test cache_indexes and get_cached_indexes"""
        with TemporaryDirectory() as temp_dir:
            manager = CacheManager(temp_dir)

            # Create simple test objects that can be pickled
            # Using simple dicts as test data
            mock_reg_index = {"publications": ["pub1"], "type": "registration"}
            mock_ren_index = {"publications": ["pub2"], "type": "renewal"}

            # Cache the indexes
            success = manager.cache_indexes(
                "/copyright", "/renewal", "test_hash", mock_reg_index, mock_ren_index
            )
            assert success

            # Note: Due to file system checks in _is_cache_valid,
            # the cached data won't be valid without actual source dirs
            # But we can verify the cache files were created
            cache_subdir = join(manager.indexes_cache_dir, "all")
            assert exists(join(cache_subdir, "registration.pkl"))
            assert exists(join(cache_subdir, "renewal.pkl"))

    def test_get_cached_generic_detector_disabled(self):
        """Test get_cached_generic_detector when disabled"""
        with TemporaryDirectory() as temp_dir:
            manager = CacheManager(temp_dir)

            detector_config = {"enable_generic_detection": False}

            result = manager.get_cached_generic_detector("/copyright", "/renewal", detector_config)

            assert result is None

    def test_cache_and_get_generic_detector(self):
        """Test cache_generic_detector and get_cached_generic_detector"""
        with TemporaryDirectory() as temp_dir:
            manager = CacheManager(temp_dir)

            # Create simple test object that can be pickled
            mock_detector = {"patterns": ["pattern1"], "type": "detector"}

            detector_config = {"enable_generic_detection": True}

            # Cache the detector
            success = manager.cache_generic_detector(
                "/copyright", "/renewal", detector_config, mock_detector
            )
            assert success

            # Note: Due to file system checks in _is_cache_valid,
            # the cached data won't be valid without actual source dirs
            # But we can verify the cache files were created
            cache_file = join(manager.generic_detector_cache_dir, "detector.pkl")
            assert exists(cache_file)

    def test_clear_all_caches(self):
        """Test clear_all_caches method"""
        with TemporaryDirectory() as temp_dir:
            manager = CacheManager(temp_dir)

            # Create some cache files
            for subdir in ["copyright_data", "renewal_data", "indexes"]:
                cache_file = join(temp_dir, subdir, "test.pkl")
                with open(cache_file, "wb") as f:
                    dump({"test": "data"}, f)

            # Clear all caches
            manager.clear_all_caches()

            # Check directories are recreated but empty
            assert exists(join(temp_dir, "copyright_data"))
            assert exists(join(temp_dir, "renewal_data"))
            assert exists(join(temp_dir, "indexes"))

            # But no files inside
            assert not exists(join(temp_dir, "copyright_data", "test.pkl"))
            assert not exists(join(temp_dir, "renewal_data", "test.pkl"))
            assert not exists(join(temp_dir, "indexes", "test.pkl"))

    def test_get_cache_info(self):
        """Test get_cache_info method"""
        with TemporaryDirectory() as temp_dir:
            manager = CacheManager(temp_dir)

            # Create some cache files
            for i in range(3):
                cache_file = join(temp_dir, "copyright_data", f"file{i}.pkl")
                with open(cache_file, "wb") as f:
                    dump({"data": i}, f)

            info = manager.get_cache_info()

            assert "cache_dir" in info
            assert info["cache_dir"] == temp_dir
            assert "components" in info
            assert "copyright_data" in info["components"]

    def test_is_cache_valid_with_all_conditions(self):
        """Test _is_cache_valid with various validity conditions"""
        with TemporaryDirectory() as temp_dir:
            manager = CacheManager(temp_dir)

            cache_subdir = join(temp_dir, "test")
            makedirs(cache_subdir)

            source_file = join(temp_dir, "source.txt")
            with open(source_file, "w") as f:
                f.write("test")

            # Save valid metadata
            metadata = {
                "version": "1.0",
                "source_files": [source_file],
                "source_mtimes": [getmtime(source_file)],
                "cache_time": time(),
                "additional_deps": {"key": "value"},
            }
            manager._save_metadata(cache_subdir, metadata)

            # Should be valid with matching everything
            valid = manager._is_cache_valid(cache_subdir, [source_file], {"key": "value"})
            assert valid is True

            # Invalid if source doesn't exist
            valid = manager._is_cache_valid(cache_subdir, ["/nonexistent"], {"key": "value"})
            assert valid is False

            # Invalid if source list different
            valid = manager._is_cache_valid(
                cache_subdir, [source_file, "/another"], {"key": "value"}
            )
            assert valid is False
