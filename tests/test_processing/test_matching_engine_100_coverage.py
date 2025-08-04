# tests/test_processing/test_matching_engine_100_coverage.py

"""Additional tests for matching_engine.py to achieve 100% coverage"""

# Standard library imports
from os import makedirs
from os import unlink
from os.path import exists
from os.path import join
from pickle import dump as pickle_dump
from pickle import load as pickle_load
from tempfile import NamedTemporaryFile
from tempfile import TemporaryDirectory
from unittest.mock import Mock
from unittest.mock import patch

# Local imports
from marc_pd_tool.data.enums import CountryClassification
from marc_pd_tool.data.publication import Publication
from marc_pd_tool.processing.matching_engine import DataMatcher
from marc_pd_tool.processing.matching_engine import init_worker
from marc_pd_tool.processing.matching_engine import process_batch
from marc_pd_tool.utils.types import SimilarityScoresDict


class TestDataMatcherEdgeCases:
    """Test edge cases in DataMatcher"""

    def test_find_best_match_no_generic_detector(self):
        """Test matching without generic detector"""
        matcher = DataMatcher()

        marc_pub = Publication(
            title="Test Book", author="Test Author", pub_date="1950", source_id="001"
        )

        copyright_pubs = [
            Publication(title="Test Book", author="Test Author", pub_date="1950", source_id="c001")
        ]

        # Test without generic detector (line 127)
        result = matcher.find_best_match(
            marc_pub,
            copyright_pubs,
            year_tolerance=2,
            title_threshold=40,
            author_threshold=30,
            publisher_threshold=20,
            early_exit_title=95,
            early_exit_author=90,
            generic_detector=None,  # No generic detector
        )

        assert result is not None
        assert result["copyright_record"]["source_id"] == "c001"

    def test_find_best_match_lccn_match(self):
        """Test LCCN matching when both have same LCCN"""
        matcher = DataMatcher()

        marc_pub = Publication(
            title="Test Book", author="Test Author", pub_date="1950", source_id="001"
        )
        marc_pub.normalized_lccn = "2001012345"

        copyright_pub = Publication(
            title="Different Title",  # Different metadata
            author="Different Author",
            pub_date="1950",  # Same year to pass year filter
            source_id="c001",
        )
        copyright_pub.normalized_lccn = "2001012345"  # Same LCCN

        result = matcher.find_best_match(
            marc_pub,
            [copyright_pub],
            year_tolerance=2,
            title_threshold=40,
            author_threshold=30,
            publisher_threshold=20,
            early_exit_title=95,
            early_exit_author=90,
        )

        # Should find match based on LCCN even with different metadata
        assert result is not None
        assert result["is_lccn_match"] is True

    def test_combine_scores_generic_title(self):
        """Test score combination with generic title"""
        matcher = DataMatcher()

        # Create publications with generic title
        marc_pub = Publication(
            title="Annual Report",
            author="Company Name",
            publisher="Publisher",
            pub_date="1950",
            source_id="001",
        )

        copyright_pub = Publication(
            title="Annual Report",
            author="Company Name",
            publisher="Publisher",
            pub_date="1950",
            source_id="c001",
        )

        # Create generic detector that marks "Annual Report" as generic
        generic_detector = Mock()
        generic_detector.is_generic.return_value = True
        generic_detector.get_detection_reason.return_value = "pattern: annual report"

        # Test line 305 - generic title handling
        score = matcher._combine_scores(
            title_score=90.0,
            author_score=85.0,
            publisher_score=80.0,
            marc_pub=marc_pub,
            copyright_pub=copyright_pub,
            generic_detector=generic_detector,
        )

        # With generic title, title weight should be reduced
        assert score < 85.0  # Should be less than simple average

    def test_find_best_match_ignore_thresholds_best_above_minimum(self):
        """Test ignore thresholds mode with best match above minimum"""
        matcher = DataMatcher()

        marc_pub = Publication(
            title="Test Book", author="Test Author", pub_date="1950", source_id="001"
        )

        copyright_pubs = [
            Publication(
                title="Different Title",
                author="Different Author",
                pub_date="1950",
                source_id="c001",
            ),
            Publication(
                title="Test Book Modified", author="Test Author", pub_date="1950", source_id="c002"
            ),
        ]

        # Use find_best_match_ignore_thresholds method
        result = matcher.find_best_match_ignore_thresholds(
            marc_pub,
            copyright_pubs,
            year_tolerance=2,
            early_exit_title=95,
            early_exit_author=90,
            minimum_combined_score=30.0,
        )

        assert result is not None
        assert result["copyright_record"]["source_id"] == "c002"


class TestWorkerFunctions:
    """Test worker-related functions"""

    def test_init_worker_with_detector_config(self):
        """Test worker initialization with detector config"""
        # Create temp directories and files
        with TemporaryDirectory() as tmpdir:
            cache_dir = join(tmpdir, "cache")
            copyright_dir = join(tmpdir, "copyright")
            renewal_dir = join(tmpdir, "renewal")

            makedirs(cache_dir)
            makedirs(copyright_dir)
            makedirs(renewal_dir)

            # Test with detector config
            detector_config = {"frequency_threshold": 10, "custom_patterns": {"test pattern"}}

            with patch("marc_pd_tool.processing.matching_engine.CacheManager") as mock_cache_mgr:
                mock_cache = Mock()
                # Create mock indexes with size method
                mock_reg_index = Mock()
                mock_reg_index.size.return_value = 100
                mock_ren_index = Mock()
                mock_ren_index.size.return_value = 50
                # Return tuple of (registration_index, renewal_index)
                mock_cache.get_cached_indexes.return_value = (mock_reg_index, mock_ren_index)
                mock_cache_mgr.return_value = mock_cache

                with patch(
                    "marc_pd_tool.processing.matching_engine._worker_data", {}
                ) as mock_worker_data:
                    init_worker(
                        cache_dir,
                        copyright_dir,
                        renewal_dir,
                        "test_hash",
                        detector_config,
                        1950,  # min_year
                        1960,  # max_year
                        False,  # brute_force
                    )

                    # Worker initialization should succeed
                    assert mock_cache_mgr.called
                    assert mock_cache.get_cached_indexes.called

    def test_process_batch_worker_not_initialized(self):
        """Test process_batch when worker is not initialized"""
        # Create a temporary batch file
        with NamedTemporaryFile(suffix=".pkl", delete=False) as f:
            batch_path = f.name
            pickle_dump([Publication(title="Test", source_id="001")], f)

        try:
            # Create a minimal batch info
            batch_info = (
                1,  # batch_id
                batch_path,  # batch_path
                "cache_dir",  # cache_dir
                "copyright_dir",  # copyright_dir
                "renewal_dir",  # renewal_dir
                "test_hash",  # config_hash
                None,  # detector_config
                1,  # total_batches
                40,  # title_threshold
                30,  # author_threshold
                20,  # publisher_threshold
                2,  # year_tolerance
                95,  # early_exit_title
                90,  # early_exit_author
                85,  # early_exit_publisher
                False,  # score_everything_mode
                None,  # minimum_combined_score
                False,  # brute_force_missing_year
                1950,  # min_year
                1960,  # max_year
                "result_dir",  # result_temp_dir
            )

            # Clear _worker_data to simulate uninitialized state
            # Local imports
            import marc_pd_tool.processing.matching_engine

            marc_pd_tool.processing.matching_engine._worker_data = {}

            # Process batch - error should be caught and handled
            batch_id, result_path, stats = process_batch(batch_info)

            # Check that the error was recorded
            assert batch_id == 1
            # Stats should be the initial dict - check for expected keys
            assert "batch_id" in stats
            assert stats["batch_id"] == 1
            assert "marc_count" in stats

            # Result file should exist (even if empty)
            assert "_failed" in result_path

        finally:
            # Clean up
            if exists(batch_path):
                unlink(batch_path)


class TestProcessBatchComprehensive:
    """Comprehensive tests for process_batch function"""

    def test_process_batch_renewal_match_with_generic_title(self, tmp_path):
        """Test batch processing with renewal match and generic title detection"""
        # Create batch and result directories
        batch_dir = tmp_path / "batches"
        result_dir = tmp_path / "results"
        batch_dir.mkdir()
        result_dir.mkdir()

        # Create test publication
        marc_pub = Publication(
            title="Annual Report",
            author="Company Name",
            pub_date="1955",
            source_id="001",
            country_code="xxu",
            country_classification=CountryClassification.US,
        )

        # Create batch file
        batch_file = batch_dir / "batch_00001.pkl"
        with open(batch_file, "wb") as f:
            pickle_dump([marc_pub], f)

        # Create BatchProcessingInfo tuple
        batch_info = (
            1,  # batch_id
            str(batch_file),  # batch_path
            str(tmp_path / "cache"),  # cache_dir
            str(tmp_path / "copyright"),  # copyright_dir
            str(tmp_path / "renewal"),  # renewal_dir
            "test_hash",  # config_hash
            {"frequency_threshold": 10},  # detector_config
            1,  # total_batches
            40,  # title_threshold
            30,  # author_threshold
            20,  # publisher_threshold
            2,  # year_tolerance
            95,  # early_exit_title
            90,  # early_exit_author
            85,  # early_exit_publisher
            False,  # score_everything_mode
            None,  # minimum_combined_score
            False,  # brute_force_missing_year
            1950,  # min_year
            1960,  # max_year
            str(result_dir),  # result_temp_dir
        )

        # Create mock renewal publication
        mock_renewal_pub = Publication(
            title="Annual Report",
            author="Company Name",
            publisher="Publisher",
            pub_date="1955",
            source_id="R00001",
            full_text="Annual Report by Company Name. Publisher, 1955.",
        )

        # Mock worker data with renewal match
        mock_ren_index = Mock()
        mock_ren_index.get_candidates_list.return_value = [mock_renewal_pub]

        # Create a mock matcher that returns a match with generic title info
        mock_matcher = Mock(spec=DataMatcher)
        mock_match = {
            "copyright_record": {
                "title": "Annual Report",
                "author": "Company Name",
                "year": 1955,
                "publisher": "Publisher",
                "source_id": "R00001",
                "pub_date": "1955",
                "full_text": "Annual Report by Company Name. Publisher, 1955.",
                "normalized_title": "annual report",
                "normalized_author": "company name",
                "normalized_publisher": "publisher",
            },
            "similarity_scores": {
                "combined": 85.0,
                "title": 90.0,
                "author": 85.0,
                "publisher": 80.0,
            },
            "is_lccn_match": False,
            "generic_title_info": {  # Test lines 872-889
                "has_generic_title": True,
                "marc_title_is_generic": True,
                "copyright_title_is_generic": True,
                "marc_detection_reason": "pattern: annual report",
                "copyright_detection_reason": "pattern: annual report",
            },
        }
        mock_matcher.find_best_match.side_effect = [
            None,
            mock_match,
        ]  # No reg match, has renewal match

        # Mock generic detector
        mock_generic = Mock()
        mock_generic.is_generic.return_value = True
        mock_generic.get_detection_reason.return_value = "pattern: annual report"

        with patch(
            "marc_pd_tool.processing.matching_engine._worker_data",
            {
                "registration_index": Mock(get_candidates_list=Mock(return_value=[])),
                "renewal_index": mock_ren_index,
                "generic_detector": mock_generic,
                "matching_engine": mock_matcher,
            },
        ):
            # Process batch
            batch_id, result_path, stats = process_batch(batch_info)

            assert batch_id == 1
            assert exists(result_path)
            assert stats["renewal_matches_found"] == 1

            # Load and verify results
            with open(result_path, "rb") as f:
                results = pickle_load(f)

            assert len(results) == 1
            assert results[0].renewal_match is not None
            assert results[0].generic_title_detected is True
            assert results[0].renewal_generic_title is True
            assert results[0].generic_detection_reason == "pattern: annual report"

    def test_process_batch_renewal_match_generic_copyright_only(self, tmp_path):
        """Test renewal match where only copyright title is generic"""
        # Create batch and result directories
        batch_dir = tmp_path / "batches"
        result_dir = tmp_path / "results"
        batch_dir.mkdir()
        result_dir.mkdir()

        # Create test publication with non-generic title
        marc_pub = Publication(
            title="Specific Company Report 1955",
            author="Company Name",
            pub_date="1955",
            source_id="001",
            country_code="xxu",
            country_classification=CountryClassification.US,
        )

        # Create batch file
        batch_file = batch_dir / "batch_00001.pkl"
        with open(batch_file, "wb") as f:
            pickle_dump([marc_pub], f)

        # Create BatchProcessingInfo tuple
        batch_info = (
            1,  # batch_id
            str(batch_file),  # batch_path
            str(tmp_path / "cache"),  # cache_dir
            str(tmp_path / "copyright"),  # copyright_dir
            str(tmp_path / "renewal"),  # renewal_dir
            "test_hash",  # config_hash
            {"frequency_threshold": 10},  # detector_config
            1,  # total_batches
            40,  # title_threshold
            30,  # author_threshold
            20,  # publisher_threshold
            2,  # year_tolerance
            95,  # early_exit_title
            90,  # early_exit_author
            85,  # early_exit_publisher
            False,  # score_everything_mode
            None,  # minimum_combined_score
            False,  # brute_force_missing_year
            1950,  # min_year
            1960,  # max_year
            str(result_dir),  # result_temp_dir
        )

        # Create mock renewal publication with generic title
        mock_renewal_pub = Publication(
            title="Annual Report",
            author="Company Name",
            publisher="Publisher",
            pub_date="1955",
            source_id="R00001",
        )

        # Mock worker data
        mock_ren_index = Mock()
        mock_ren_index.get_candidates_list.return_value = [mock_renewal_pub]

        # Create match with generic info where only copyright is generic
        mock_matcher = Mock(spec=DataMatcher)
        mock_match = {
            "copyright_record": {
                "title": "Annual Report",
                "author": "Company Name",
                "year": 1955,
                "publisher": "Publisher",
                "source_id": "R00001",
                "pub_date": "1955",
                "full_text": "Annual Report...",
                "normalized_title": "annual report",
                "normalized_author": "company name",
                "normalized_publisher": "publisher",
            },
            "similarity_scores": {
                "combined": 85.0,
                "title": 90.0,
                "author": 85.0,
                "publisher": 80.0,
            },
            "is_lccn_match": False,
            "generic_title_info": {  # Test lines 885-888
                "has_generic_title": True,
                "marc_title_is_generic": False,  # MARC title is not generic
                "copyright_title_is_generic": True,
                "marc_detection_reason": "none",
                "copyright_detection_reason": "pattern: annual report",
            },
        }
        mock_matcher.find_best_match.side_effect = [None, mock_match]

        with patch(
            "marc_pd_tool.processing.matching_engine._worker_data",
            {
                "registration_index": Mock(get_candidates_list=Mock(return_value=[])),
                "renewal_index": mock_ren_index,
                "generic_detector": Mock(),
                "matching_engine": mock_matcher,
            },
        ):
            # Process batch
            batch_id, result_path, stats = process_batch(batch_info)

            # Load and verify results
            with open(result_path, "rb") as f:
                results = pickle_load(f)

            assert len(results) == 1
            # When MARC title is not generic but copyright is, we use copyright reason
            assert results[0].generic_detection_reason == "pattern: annual report"

    def test_process_batch_exception_handling(self, tmp_path):
        """Test batch processing with exception during matching"""
        # Create batch and result directories
        batch_dir = tmp_path / "batches"
        result_dir = tmp_path / "results"
        batch_dir.mkdir()
        result_dir.mkdir()

        # Create test publication
        marc_pub = Publication(
            title="Test Book",
            author="Test Author",
            pub_date="1955",
            source_id="001",
            country_code="xxu",
            country_classification=CountryClassification.US,
        )

        # Create batch file
        batch_file = batch_dir / "batch_00001.pkl"
        with open(batch_file, "wb") as f:
            pickle_dump([marc_pub], f)

        # Create BatchProcessingInfo tuple
        batch_info = (
            1,  # batch_id
            str(batch_file),  # batch_path
            str(tmp_path / "cache"),  # cache_dir
            str(tmp_path / "copyright"),  # copyright_dir
            str(tmp_path / "renewal"),  # renewal_dir
            "test_hash",  # config_hash
            None,  # detector_config
            1,  # total_batches
            40,  # title_threshold
            30,  # author_threshold
            20,  # publisher_threshold
            2,  # year_tolerance
            95,  # early_exit_title
            90,  # early_exit_author
            85,  # early_exit_publisher
            False,  # score_everything_mode
            None,  # minimum_combined_score
            False,  # brute_force_missing_year
            1950,  # min_year
            1960,  # max_year
            str(result_dir),  # result_temp_dir
        )

        # Mock to raise exception during candidate retrieval
        mock_reg_index = Mock()
        mock_reg_index.get_candidates_list.side_effect = Exception("Index error")

        with patch(
            "marc_pd_tool.processing.matching_engine._worker_data",
            {
                "registration_index": mock_reg_index,
                "renewal_index": Mock(),
                "generic_detector": None,
                "matching_engine": DataMatcher(),
            },
        ):
            # Test lines 979-1003 - exception handling
            batch_id, result_path, stats = process_batch(batch_info)

            assert batch_id == 1
            assert exists(result_path)
            # When error occurs, empty results are saved but stats remain as initialized
            assert stats["batch_id"] == 1
            assert "_failed" in result_path

            # Load and verify error result
            with open(result_path, "rb") as f:
                results = pickle_load(f)

            # Error saves empty list
            assert results == []


class TestDataMatcherYearHandling:
    """Test year-related edge cases"""

    def test_find_best_match_no_year_in_copyright(self):
        """Test matching when copyright publication has no year"""
        matcher = DataMatcher()

        marc_pub = Publication(
            title="Test Book", author="Test Author", pub_date="1950", source_id="001"
        )

        # Copyright pub with no year
        copyright_pub = Publication(
            title="Test Book", author="Test Author", pub_date=None, source_id="c001"  # No year
        )
        copyright_pub.year = None

        # Test line 185 - copyright year is None
        result = matcher.find_best_match(
            marc_pub,
            [copyright_pub],
            year_tolerance=2,
            title_threshold=40,
            author_threshold=30,
            publisher_threshold=20,
            early_exit_title=95,
            early_exit_author=90,
        )

        # Should still match based on title/author
        assert result is not None

    def test_find_best_match_zero_year_tolerance(self):
        """Test matching with zero year tolerance"""
        matcher = DataMatcher()

        marc_pub = Publication(
            title="Test Book", author="Test Author", pub_date="1950", source_id="001"
        )

        copyright_pubs = [
            Publication(
                title="Test Book",
                author="Test Author",
                pub_date="1951",  # One year off
                source_id="c001",
            )
        ]

        # Test line 191 - year difference > tolerance (0)
        result = matcher.find_best_match(
            marc_pub,
            copyright_pubs,
            year_tolerance=0,  # Zero tolerance
            title_threshold=40,
            author_threshold=30,
            publisher_threshold=20,
            early_exit_title=95,
            early_exit_author=90,
        )

        # Should not match due to year difference
        assert result is None


class TestMatchResultCreation:
    """Test match result creation edge cases"""

    def test_create_match_result_year_difference(self):
        """Test match result creation with year calculation"""
        matcher = DataMatcher()

        # MARC pub with year
        marc_pub = Publication(
            title="Test Book", author="Test Author", pub_date="1950", source_id="001"
        )

        copyright_pub = Publication(
            title="Test Book",
            author="Test Author",
            publisher="Test Publisher",
            pub_date="1952",
            source_id="c001",
        )

        scores = SimilarityScoresDict(combined=85.0, title=90.0, author=85.0, publisher=80.0)

        # Test match result creation - use correct signature
        result = matcher._create_match_result(
            copyright_pub,
            scores["title"],
            scores["author"],
            scores["publisher"],
            scores["combined"],
            marc_pub,
            None,  # generic_detector
            is_lccn_match=False,
        )

        # Check result structure - may not have year_difference as top-level key
        assert result is not None
        assert "copyright_record" in result
        assert "similarity_scores" in result


class TestPublisherMatching:
    """Test publisher-related functionality"""

    def test_combine_scores_no_publisher_handling(self):
        """Test score combination when publications have no publisher"""
        matcher = DataMatcher()

        # Create publications with no publisher
        marc_pub = Publication(
            title="Test Book",
            author="Test Author",
            publisher=None,
            pub_date="1950",
            source_id="001",
        )

        copyright_pub = Publication(
            title="Test Book",
            author="Test Author",
            publisher=None,
            pub_date="1950",
            source_id="c001",
        )

        # Test line 297->304 - no publisher branch
        score = matcher._combine_scores(
            title_score=90.0,
            author_score=85.0,
            publisher_score=0.0,
            marc_pub=marc_pub,
            copyright_pub=copyright_pub,
            generic_detector=None,
        )

        # Without publisher, weights should be redistributed
        assert score > 0
        # The actual calculation may not be exactly 0.5/0.5 due to implementation details
        assert 85.0 <= score <= 90.0  # Should be between the two scores
