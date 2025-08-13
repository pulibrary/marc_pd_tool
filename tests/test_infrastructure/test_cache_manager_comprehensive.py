# tests/test_infrastructure/test_cache_manager_comprehensive.py

"""Comprehensive tests for CacheManager to improve coverage"""

# Standard library imports
import json
import os
import pickle
import time
from unittest.mock import patch

# Third party imports
import pytest

# Local imports
from marc_pd_tool.core.domain.publication import Publication
from marc_pd_tool.core.types.results import CacheMetadata
from marc_pd_tool.infrastructure import CacheManager


class TestCacheManagerDirectoryOperations:
    """Test directory-related operations in CacheManager"""

    def test_get_directory_modification_time_nonexistent(self):
        """Test getting modification time for non-existent directory"""
        cache_mgr = CacheManager()

        # Non-existent directory should return 0
        mtime = cache_mgr._get_directory_modification_time("/nonexistent/path")
        assert mtime == 0.0

    def test_get_directory_modification_time_with_error(self):
        """Test modification time when walk raises error"""
        cache_mgr = CacheManager()

        with (
            patch("os.path.exists", return_value=True),
            patch("os.path.getmtime", return_value=123456.0),
            patch("os.walk", side_effect=OSError("Permission denied")),
        ):

            # Should return 0 on error
            mtime = cache_mgr._get_directory_modification_time("/some/path")
            assert mtime == 0.0

    def test_get_directory_modification_time_nested_files(self, tmp_path):
        """Test getting latest modification time from nested directories"""
        cache_mgr = CacheManager()

        # Create nested structure
        subdir = tmp_path / "subdir"
        subdir.mkdir()

        # Create files with different mtimes
        file1 = tmp_path / "file1.txt"
        file2 = subdir / "file2.txt"

        file1.write_text("content1")
        time.sleep(0.1)  # Ensure different mtime
        file2.write_text("content2")

        # Get modification time
        mtime = cache_mgr._get_directory_modification_time(str(tmp_path))

        # Should be the latest (file2's) mtime
        assert mtime >= file1.stat().st_mtime
        assert mtime >= file2.stat().st_mtime


class TestCacheManagerYearRangeOperations:
    """Test year-range specific caching functionality"""

    def test_get_year_range_cache_filename_variations(self):
        """Test cache filename generation with different parameters"""
        cache_mgr = CacheManager()

        # No year range
        filename = cache_mgr._get_year_range_cache_filename("publications")
        assert filename == "publications_all.pkl"

        # Min year only
        filename = cache_mgr._get_year_range_cache_filename("publications", min_year=1950)
        assert filename == "publications_1950_present.pkl"

        # Max year only
        filename = cache_mgr._get_year_range_cache_filename("publications", max_year=1960)
        assert filename == "publications_earliest_1960.pkl"

        # Both years
        filename = cache_mgr._get_year_range_cache_filename(
            "publications", min_year=1950, max_year=1960
        )
        assert filename == "publications_1950_1960.pkl"

        # Brute force mode
        filename = cache_mgr._get_year_range_cache_filename("publications", brute_force=True)
        assert filename == "publications_all.pkl"

    def test_cache_copyright_data_year_filtered(self, tmp_path):
        """Test caching copyright data with year filtering"""
        cache_mgr = CacheManager(str(tmp_path))

        # Create test publications
        pubs = [
            Publication(title="Book 1950", pub_date="1950", source_id="001"),
            Publication(title="Book 1955", pub_date="1955", source_id="002"),
            Publication(title="Book 1960", pub_date="1960", source_id="003"),
        ]

        # Cache with year range
        success = cache_mgr.cache_copyright_data(
            "/source/copyright", pubs, min_year=1950, max_year=1955
        )

        assert success

        # Verify cache file was created with correct name - it's in a subdirectory
        cache_file = tmp_path / "copyright_data" / "1950_1955" / "publications_1950_1955.pkl"
        assert cache_file.exists()

        # Load and verify
        with open(cache_file, "rb") as f:
            cached_pubs = pickle.load(f)

        assert len(cached_pubs) == 3  # All pubs cached regardless of filter

    def test_get_cached_copyright_data_year_specific(self, tmp_path):
        """Test retrieving year-specific cached data"""
        cache_mgr = CacheManager(str(tmp_path))

        # Create a fake source directory
        source_dir = tmp_path / "source"
        source_dir.mkdir()

        # Create and cache publications for different year ranges
        pubs_50s = [Publication(title="50s Book", pub_date="1955", source_id="001")]
        pubs_60s = [Publication(title="60s Book", pub_date="1965", source_id="002")]

        cache_mgr.cache_copyright_data(str(source_dir), pubs_50s, min_year=1950, max_year=1959)
        cache_mgr.cache_copyright_data(str(source_dir), pubs_60s, min_year=1960, max_year=1969)

        # Make the source directory older than the cache
        old_time = time.time() - 86400  # 1 day old
        os.utime(source_dir, (old_time, old_time))

        # Retrieve specific year range
        cached = cache_mgr.get_cached_copyright_data(str(source_dir), min_year=1950, max_year=1959)

        assert cached is not None
        assert len(cached) == 1
        assert cached[0].title == "50s Book"  # Minimal cleanup only


class TestCacheManagerIndexOperations:
    """Test index caching operations"""

    def test_get_cached_indexes_corrupt_file(self, tmp_path):
        """Test handling corrupt index cache files"""
        cache_mgr = CacheManager(str(tmp_path))

        # Create cache subdirectory for "all" years
        cache_subdir = tmp_path / "indexes" / "all"
        cache_subdir.mkdir(parents=True, exist_ok=True)

        # Create corrupt cache files
        reg_file = cache_subdir / "registration.pkl"
        ren_file = cache_subdir / "renewal.pkl"

        reg_file.write_bytes(b"corrupt data")
        ren_file.write_bytes(b"corrupt data")

        # Should return None on corrupt data
        result = cache_mgr.get_cached_indexes("/dummy/copyright", "/dummy/renewal", "test_hash")

        assert result is None


class TestCacheManagerGenericDetector:
    """Test generic title detector caching"""

    def test_get_cached_generic_detector_disabled(self, tmp_path):
        """Test generic detector when disabled in config"""
        cache_mgr = CacheManager(str(tmp_path))

        # Config with disabled detector
        config = {"disabled": True}

        result = cache_mgr.get_cached_generic_detector("/dummy/copyright", "/dummy/renewal", config)

        # Should return None when disabled
        assert result is None


class TestCacheManagerMARCOperations:
    """Test MARC data caching operations"""

    def test_cache_marc_publications(self, tmp_path):
        """Test caching MARC publications"""
        cache_mgr = CacheManager(str(tmp_path))

        # Create test publications
        pubs = [
            Publication(title="MARC Book 1", source_id="M001"),
            Publication(title="MARC Book 2", source_id="M002"),
        ]

        # Create batches
        batches = [pubs]

        # Cache publications
        year_ranges = {"copyright": (1950, 1960), "renewal": (1950, 1960)}
        filtering_options = {"us_only": True, "min_year": 1950, "max_year": 1960}

        success = cache_mgr.cache_marc_data(
            "test_marc.xml", year_ranges, filtering_options, batches
        )

        assert success

        # Verify cache file
        cache_file = tmp_path / "marc_data" / "batches.pkl"
        assert cache_file.exists()

    def test_get_cached_marc_data_missing(self, tmp_path):
        """Test retrieving MARC cache when file doesn't exist"""
        cache_mgr = CacheManager(str(tmp_path))

        # Non-existent MARC file
        year_ranges = {"copyright": (1950, 1960), "renewal": (1950, 1960)}
        filtering_options = {"us_only": True, "min_year": 1950, "max_year": 1960}

        result = cache_mgr.get_cached_marc_data(
            "/nonexistent/marc.xml", year_ranges, filtering_options
        )

        assert result is None

    def test_get_cached_marc_data_stale(self, tmp_path):
        """Test retrieving stale MARC cache"""
        cache_mgr = CacheManager(str(tmp_path))

        # Create MARC file
        marc_file = tmp_path / "test.xml"
        marc_file.write_text("<records/>")

        # Cache some data first
        pubs = [Publication(title="Old", source_id="001")]
        batches = [pubs]
        year_ranges = {"copyright": (1950, 1960), "renewal": (1950, 1960)}
        filtering_options = {"us_only": True, "min_year": 1950, "max_year": 1960}

        cache_mgr.cache_marc_data(str(marc_file), year_ranges, filtering_options, batches)

        # Find the created cache file
        cache_file = tmp_path / "marc_data" / "batches.pkl"
        assert cache_file.exists()

        # Make cache older than source
        old_time = marc_file.stat().st_mtime - 100
        os.utime(cache_file, (old_time, old_time))

        # Should return None for stale cache
        result = cache_mgr.get_cached_marc_data(str(marc_file), year_ranges, filtering_options)
        assert result is None


class TestCacheManagerMetadata:
    """Test cache metadata operations"""

    def test_save_and_load_cache_metadata(self, tmp_path):
        """Test saving and loading cache metadata"""
        cache_mgr = CacheManager(str(tmp_path))

        # Create test data and cache it
        pubs = [Publication(title="Test", source_id="001")]

        # Test internal metadata handling through public API
        cache_mgr.cache_copyright_data("/source/path", pubs)

        # Verify metadata file was created - it's in a subdirectory
        metadata_file = tmp_path / "copyright_data" / "all" / "metadata.json"
        assert metadata_file.exists()

        # Load and check metadata structure
        with open(metadata_file, "r") as f:
            metadata = json.load(f)

        assert "version" in metadata
        assert "source_files" in metadata
        assert metadata["source_files"] == ["/source/path"]

    def test_get_cache_info(self, tmp_path):
        """Test getting cache information"""
        cache_mgr = CacheManager(str(tmp_path))

        # Cache directories are already created by CacheManager init

        # Add some files
        (tmp_path / "copyright_data" / "test1.pkl").write_bytes(b"x" * 1000)
        (tmp_path / "renewal_data" / "test2.pkl").write_bytes(b"x" * 2000)
        (tmp_path / "indexes" / "test3.pkl").write_bytes(b"x" * 3000)

        # Get cache info
        info = cache_mgr.get_cache_info()

        assert "cache_dir" in info
        assert "cache_exists" in info
        assert info["cache_exists"] is True
        assert "components" in info
        assert "copyright_data" in info["components"]
        assert "renewal_data" in info["components"]
        assert "indexes" in info["components"]

    def test_clear_all_caches(self, tmp_path):
        """Test clearing all caches"""
        cache_mgr = CacheManager(str(tmp_path))

        # Create cache files
        for subdir in [
            "copyright_data",
            "renewal_data",
            "indexes",
            "marc_data",
            "generic_detector",
        ]:
            dir_path = tmp_path / subdir
            dir_path.mkdir(parents=True, exist_ok=True)
            (dir_path / "test.pkl").write_bytes(b"data")

        # Clear all
        cache_mgr.clear_all_caches()

        # All files should be gone
        for subdir in [
            "copyright_data",
            "renewal_data",
            "indexes",
            "marc_data",
            "generic_detector",
        ]:
            assert not list((tmp_path / subdir).glob("*.pkl"))


class TestCacheManagerErrorHandling:
    """Test error handling in cache manager"""

    def test_cache_directory_creation_failure(self):
        """Test handling directory creation failures"""
        # The CacheManager now raises on directory creation failure
        with patch("os.makedirs", side_effect=OSError("Permission denied")):
            with pytest.raises(OSError, match="Permission denied"):
                CacheManager("/invalid/path")

    def test_pickle_load_error_handling(self, tmp_path):
        """Test handling pickle load errors"""
        cache_mgr = CacheManager(str(tmp_path))

        # Create corrupt pickle file in subdirectory
        cache_file = tmp_path / "copyright_data" / "all" / "publications_all.pkl"
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_bytes(b"not pickle data")

        # Should handle gracefully
        with patch("os.path.getmtime", return_value=0):
            result = cache_mgr.get_cached_copyright_data("/dummy")

        assert result is None

    def test_file_write_error_handling(self, tmp_path):
        """Test handling file write errors"""
        cache_mgr = CacheManager(str(tmp_path))

        # Make the subdirectory read-only
        cache_subdir = tmp_path / "copyright_data" / "all"
        cache_subdir.mkdir(parents=True, exist_ok=True)
        cache_subdir.chmod(0o555)

        try:
            # Try to cache - should handle error
            pubs = [Publication(title="Test", source_id="001")]

            # This should not raise, but return False
            success = cache_mgr.cache_copyright_data("/source", pubs)
            assert not success

        finally:
            # Restore permissions for cleanup
            cache_subdir.chmod(0o755)

    def test_save_metadata_error_handling(self, tmp_path):
        """Test metadata save error handling"""
        cache_mgr = CacheManager(str(tmp_path))

        # Test internal method with invalid metadata
        metadata: CacheMetadata = {
            "version": "1.0",
            "source_files": ["/test"],
            "source_mtimes": [1000.0],
            "cache_time": time.time(),
            "additional_deps": {},
        }

        # Make metadata file unwritable
        metadata_dir = tmp_path / "copyright_data" / "all"
        metadata_dir.mkdir(parents=True, exist_ok=True)
        metadata_file = metadata_dir / "metadata.json"
        metadata_file.write_text("{}")
        metadata_file.chmod(0o444)

        try:
            # Save should handle error gracefully
            cache_mgr._save_metadata(str(metadata_dir), metadata)
        finally:
            metadata_file.chmod(0o644)

    def test_get_cached_renewal_data(self, tmp_path):
        """Test getting cached renewal data"""
        cache_mgr = CacheManager(str(tmp_path))

        # Create a fake source directory
        source_dir = tmp_path / "source" / "renewal"
        source_dir.mkdir(parents=True)

        # Cache some renewal data
        pubs = [
            Publication(title="Renewal 1", source_id="R001"),
            Publication(title="Renewal 2", source_id="R002"),
        ]

        success = cache_mgr.cache_renewal_data(str(source_dir), pubs)
        assert success

        # Make the source directory older than the cache
        old_time = time.time() - 86400  # 1 day old
        os.utime(source_dir, (old_time, old_time))

        # Retrieve it
        cached = cache_mgr.get_cached_renewal_data(str(source_dir))

        assert cached is not None
        assert len(cached) == 2
        assert cached[0].title == "Renewal 1"  # Minimal cleanup only

    def test_cache_validity_with_dependencies(self, tmp_path):
        """Test cache validity checking with year ranges"""
        cache_mgr = CacheManager(str(tmp_path))

        # Create a fake source directory
        source_dir = tmp_path / "source"
        source_dir.mkdir()

        # Cache with specific year range
        pubs = [Publication(title="Test", source_id="001")]

        cache_mgr.cache_copyright_data(str(source_dir), pubs, min_year=1950, max_year=1960)

        # Make the source directory older than the cache
        old_time = time.time() - 86400  # 1 day old
        os.utime(source_dir, (old_time, old_time))

        # Should be valid with same year range
        cached = cache_mgr.get_cached_copyright_data(str(source_dir), min_year=1950, max_year=1960)
        assert cached is not None

        # Should be invalid with different year range
        cached = cache_mgr.get_cached_copyright_data(str(source_dir), min_year=1940, max_year=1950)
        assert cached is None

    def test_load_metadata_corrupt(self, tmp_path):
        """Test loading corrupt metadata"""
        cache_mgr = CacheManager(str(tmp_path))

        # Create corrupt metadata file
        metadata_dir = tmp_path / "copyright_data" / "all"
        metadata_dir.mkdir(parents=True, exist_ok=True)
        metadata_file = metadata_dir / "metadata.json"
        metadata_file.write_text("not valid json{")

        # Load should handle error
        metadata = cache_mgr._load_metadata(str(metadata_dir))
        assert metadata is None
