# tests/test_processing/test_skip_no_year_records.py

"""Tests for skipping MARC records without year data"""

# Standard library imports

# Third party imports
from pytest import fixture

# Local imports
from marc_pd_tool.data.publication import Publication
from marc_pd_tool.processing.matching_engine import process_batch


class TestSkipNoYearRecords:
    """Test that MARC records without year data are handled correctly"""

    @fixture
    def mock_batch_info_with_year(self, tmp_path):
        """Create batch info with MARC records that have year data"""
        # Create minimal cache directory structure
        cache_dir = tmp_path / "test_cache"
        cache_dir.mkdir()

        marc_pub_with_year = Publication(
            title="Test Book With Year",
            author="Smith, John",
            pub_date="2023",
            source="MARC",
            source_id="test001",
        )

        batch_info = (
            1,  # batch_id
            [marc_pub_with_year],  # marc_batch
            str(cache_dir),  # cache_dir
            "copyright_dir",  # copyright_dir
            "renewal_dir",  # renewal_dir
            "config_hash",  # config_hash
            {"disabled": True},  # detector_config - disable generic detector for tests
            1,  # total_batches
            40,  # title_threshold
            30,  # author_threshold
            1,  # year_tolerance
            95,  # early_exit_title
            90,  # early_exit_author
            False,  # score_everything
            40,  # minimum_combined_score
            False,  # brute_force_missing_year (default: skip no-year records)
        )
        return batch_info

    @fixture
    def mock_batch_info_no_year(self, tmp_path):
        """Create batch info with MARC records that lack year data"""
        # Create minimal cache directory structure
        cache_dir = tmp_path / "test_cache"
        cache_dir.mkdir()

        marc_pub_no_year = Publication(
            title="Test Book Without Year",
            author="Jones, Jane",
            pub_date=None,  # No year
            source="MARC",
            source_id="test002",
        )

        batch_info = (
            1,  # batch_id
            [marc_pub_no_year],  # marc_batch
            str(cache_dir),  # cache_dir
            "copyright_dir",  # copyright_dir
            "renewal_dir",  # renewal_dir
            "config_hash",  # config_hash
            {"disabled": True},  # detector_config - disable generic detector for tests
            1,  # total_batches
            40,  # title_threshold
            30,  # author_threshold
            1,  # year_tolerance
            95,  # early_exit_title
            90,  # early_exit_author
            False,  # score_everything
            40,  # minimum_combined_score
            False,  # brute_force_missing_year (default: skip no-year records)
        )
        return batch_info

    @fixture
    def mock_batch_info_mixed(self, tmp_path):
        """Create batch info with both year and no-year MARC records"""
        # Create minimal cache directory structure
        cache_dir = tmp_path / "test_cache"
        cache_dir.mkdir()

        marc_pub_with_year = Publication(
            title="Book With Year",
            author="Smith, John",
            pub_date="2023",
            source="MARC",
            source_id="test001",
        )

        marc_pub_no_year = Publication(
            title="Book Without Year",
            author="Jones, Jane",
            pub_date=None,  # No year
            source="MARC",
            source_id="test002",
        )

        batch_info = (
            1,  # batch_id
            [marc_pub_with_year, marc_pub_no_year],  # marc_batch
            str(cache_dir),  # cache_dir
            "copyright_dir",  # copyright_dir
            "renewal_dir",  # renewal_dir
            "config_hash",  # config_hash
            {"disabled": True},  # detector_config - disable generic detector for tests
            1,  # total_batches
            40,  # title_threshold
            30,  # author_threshold
            1,  # year_tolerance
            95,  # early_exit_title
            90,  # early_exit_author
            False,  # score_everything
            40,  # minimum_combined_score
            False,  # brute_force_missing_year (default: skip no-year records)
        )
        return batch_info

    def test_skip_records_without_year_by_default(self, mock_batch_info_no_year, monkeypatch):
        """Test that records without year are skipped by default"""

        # Mock the cache manager and indexes to avoid actual file operations
        def mock_get_cached_indexes(*args):
            # Return mock indexes
            class MockIndex:
                def get_candidates_list(self, pub, tolerance):
                    return []

                def get_stats(self):
                    return {"title_keys": 0, "author_keys": 0}

                def size(self):
                    return 0

            return MockIndex(), MockIndex()

        def mock_get_cached_generic_detector(*args):
            return None

        # Patch the CacheManager methods
        monkeypatch.setattr(
            "marc_pd_tool.processing.matching_engine.CacheManager.get_cached_indexes",
            mock_get_cached_indexes,
        )
        monkeypatch.setattr(
            "marc_pd_tool.processing.matching_engine.CacheManager.get_cached_generic_detector",
            mock_get_cached_generic_detector,
        )

        # Process the batch
        batch_id, processed_pubs, stats = process_batch(mock_batch_info_no_year)

        # The record should be skipped, so no publications should be processed
        assert len(processed_pubs) == 0
        assert stats["marc_count"] == 0
        assert stats["registration_matches_found"] == 0
        assert stats["renewal_matches_found"] == 0

    def test_process_records_without_year_with_brute_force(
        self, mock_batch_info_no_year, monkeypatch
    ):
        """Test that records without year are processed when brute-force option is enabled"""
        # Enable brute force mode
        batch_info_list = list(mock_batch_info_no_year)
        batch_info_list[-1] = True  # Set brute_force_missing_year to True
        batch_info_brute_force = tuple(batch_info_list)

        # Mock the cache manager and indexes
        def mock_get_cached_indexes(*args):
            class MockIndex:
                def get_candidates_list(self, pub, tolerance):
                    return []

                def get_stats(self):
                    return {"title_keys": 0, "author_keys": 0}

                def size(self):
                    return 0

                def size(self):
                    return 0

            return MockIndex(), MockIndex()

        def mock_get_cached_generic_detector(*args):
            return None

        # Patch the CacheManager methods
        monkeypatch.setattr(
            "marc_pd_tool.processing.matching_engine.CacheManager.get_cached_indexes",
            mock_get_cached_indexes,
        )
        monkeypatch.setattr(
            "marc_pd_tool.processing.matching_engine.CacheManager.get_cached_generic_detector",
            mock_get_cached_generic_detector,
        )

        # Process the batch
        batch_id, processed_pubs, stats = process_batch(batch_info_brute_force)

        # The record should be processed even without a year
        assert len(processed_pubs) == 1
        assert stats["marc_count"] == 1
        assert processed_pubs[0].original_title == "Test Book Without Year"

    def test_mixed_batch_skips_only_no_year_records(self, mock_batch_info_mixed, monkeypatch):
        """Test that only records without year are skipped in a mixed batch"""

        # Mock the cache manager and indexes
        def mock_get_cached_indexes(*args):
            class MockIndex:
                def get_candidates_list(self, pub, tolerance):
                    return []

                def get_stats(self):
                    return {"title_keys": 0, "author_keys": 0}

                def size(self):
                    return 0

            return MockIndex(), MockIndex()

        def mock_get_cached_generic_detector(*args):
            return None

        # Patch the CacheManager methods
        monkeypatch.setattr(
            "marc_pd_tool.processing.matching_engine.CacheManager.get_cached_indexes",
            mock_get_cached_indexes,
        )
        monkeypatch.setattr(
            "marc_pd_tool.processing.matching_engine.CacheManager.get_cached_generic_detector",
            mock_get_cached_generic_detector,
        )

        # Process the batch
        batch_id, processed_pubs, stats = process_batch(mock_batch_info_mixed)

        # Only the record with a year should be processed
        assert len(processed_pubs) == 1
        assert stats["marc_count"] == 1
        assert processed_pubs[0].original_title == "Book With Year"
        assert processed_pubs[0].year == 2023

    def test_brute_force_match_type_for_no_year_records(self, mock_batch_info_no_year, monkeypatch):
        """Test that matches for no-year records get 'brute_force_without_year' match type"""
        # Enable brute force mode
        batch_info_list = list(mock_batch_info_no_year)
        batch_info_list[-1] = True  # Set brute_force_missing_year to True
        batch_info_brute_force = tuple(batch_info_list)

        # Mock the cache manager and indexes to return a match
        def mock_get_cached_indexes(*args):
            class MockIndex:
                def get_candidates_list(self, pub, tolerance):
                    # Return a mock candidate that will match
                    mock_candidate = Publication(
                        title="Test Book Without Year",
                        author="Jones, Jane",
                        pub_date="1950",
                        source="Registration",
                        source_id="reg001",
                    )
                    return [mock_candidate]

                def get_stats(self):
                    return {"title_keys": 0, "author_keys": 0}

                def size(self):
                    return 1

            return MockIndex(), MockIndex()

        def mock_get_cached_generic_detector(*args):
            return None

        # Patch the CacheManager methods
        monkeypatch.setattr(
            "marc_pd_tool.processing.matching_engine.CacheManager.get_cached_indexes",
            mock_get_cached_indexes,
        )
        monkeypatch.setattr(
            "marc_pd_tool.processing.matching_engine.CacheManager.get_cached_generic_detector",
            mock_get_cached_generic_detector,
        )

        # Also need to mock the matching engine's find_best_match to return a match
        def mock_find_best_match(self, marc_pub, candidates, *args, **kwargs):
            if candidates:
                return {
                    "copyright_record": {
                        "title": candidates[0].original_title,
                        "author": candidates[0].original_author,
                        "publisher": candidates[0].original_publisher,
                        "pub_date": candidates[0].pub_date,
                        "source_id": candidates[0].source_id,
                        "year": candidates[0].year,
                        "full_text": (
                            f"{candidates[0].original_title} by {candidates[0].original_author}"  # For renewal matching
                        ),
                    },
                    "similarity_scores": {
                        "title": 100.0,
                        "author": 100.0,
                        "publisher": 50.0,
                        "combined": 100.0,
                    },
                    "is_lccn_match": False,
                }
            return None

        monkeypatch.setattr(
            "marc_pd_tool.processing.matching_engine.DataMatcher.find_best_match",
            mock_find_best_match,
        )

        # Process the batch
        batch_id, processed_pubs, stats = process_batch(batch_info_brute_force)

        # Check that the match was found and has the correct match type
        assert len(processed_pubs) == 1
        assert processed_pubs[0].registration_match is not None
        assert processed_pubs[0].registration_match.match_type == "brute_force_without_year"
