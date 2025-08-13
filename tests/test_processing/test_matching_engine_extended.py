# tests/test_processing/test_matching_engine_extended.py

"""Additional tests for matching_engine.py to reach 100% coverage"""

# Standard library imports
import os
import pickle
from unittest.mock import Mock
from unittest.mock import patch

# Third party imports
import pytest

# Local imports
from marc_pd_tool.application.processing.matching._score_combiner import ScoreCombiner
from marc_pd_tool.application.processing.matching_engine import DataMatcher
from marc_pd_tool.application.processing.matching_engine import process_batch
from marc_pd_tool.core.domain.enums import CountryClassification
from marc_pd_tool.core.domain.publication import Publication
from marc_pd_tool.infrastructure.config import get_config


class TestProcessBatch:
    """Test process_batch function"""

    def setup_method(self):
        """Ensure worker globals are reset before each test"""
        # Local imports
        import marc_pd_tool.application.processing.matching_engine

        # Initialize worker globals
        marc_pd_tool.application.processing.matching_engine._worker_registration_index = None
        marc_pd_tool.application.processing.matching_engine._worker_renewal_index = None
        marc_pd_tool.application.processing.matching_engine._worker_generic_detector = None
        marc_pd_tool.application.processing.matching_engine._worker_config = None
        marc_pd_tool.application.processing.matching_engine._worker_options = None

    def test_process_batch_success(self, tmp_path):
        """Test successful batch processing"""
        # Create batch and result directories
        batch_dir = tmp_path / "batches"
        result_dir = tmp_path / "results"
        batch_dir.mkdir()
        result_dir.mkdir()

        # Create test publications
        publications = [
            Publication(
                title="Book 1",
                author="Author 1",
                pub_date="1955",
                source_id="001",
                country_code="xxu",
                country_classification=CountryClassification.US,
            ),
            Publication(
                title="Book 2",
                author="Author 2",
                pub_date="1960",
                source_id="002",
                country_code="xxu",
                country_classification=CountryClassification.US,
            ),
        ]

        # Create batch file
        batch_file = batch_dir / "batch_00001.pkl"
        with open(batch_file, "wb") as f:
            pickle.dump(publications, f)

        # Create BatchProcessingInfo tuple (20 fields)
        batch_info = (
            1,  # batch_id
            str(batch_file),  # batch_path
            str(tmp_path / "cache"),  # cache_dir
            str(tmp_path / "copyright"),  # copyright_dir
            str(tmp_path / "renewal"),  # renewal_dir
            "test_hash",  # config_hash
            {"min_length": 10},  # detector_config
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

        # Create mock indexes that return empty lists for no matches
        mock_reg_index = Mock()
        mock_reg_index.find_candidates = Mock(return_value=[])
        mock_reg_index.publications = []

        mock_ren_index = Mock()
        mock_ren_index.find_candidates = Mock(return_value=[])
        mock_ren_index.publications = []

        # Create a real DataMatcher instance
        DataMatcher()

        # Import the module
        # Local imports
        import marc_pd_tool.application.processing.matching_engine

        # Patch worker globals at the module level
        with (
            patch.object(
                marc_pd_tool.application.processing.matching_engine,
                "_worker_registration_index",
                mock_reg_index,
            ),
            patch.object(
                marc_pd_tool.application.processing.matching_engine,
                "_worker_renewal_index",
                mock_ren_index,
            ),
            patch.object(
                marc_pd_tool.application.processing.matching_engine,
                "_worker_generic_detector",
                Mock(is_generic=Mock(return_value=False)),
            ),
            patch.object(
                marc_pd_tool.application.processing.matching_engine, "_worker_config", None
            ),
        ):
            # Process batch
            batch_id, result_path, stats = process_batch(batch_info)

            assert batch_id == 1
            assert os.path.exists(result_path)
            # Stats is now a BatchStats Pydantic model
            # Local imports
            from marc_pd_tool.application.models.batch_stats import BatchStats

            assert isinstance(stats, BatchStats)
            assert stats.batch_id == 1
            assert stats.marc_count == 2
            assert stats.registration_matches_found == 0
            assert stats.renewal_matches_found == 0

    def test_process_batch_with_matches(self, tmp_path):
        """Test batch processing with actual matches"""
        # Create batch and result directories
        batch_dir = tmp_path / "batches"
        result_dir = tmp_path / "results"
        batch_dir.mkdir()
        result_dir.mkdir()

        # Create test publication
        marc_pub = Publication(
            title="The Great Gatsby",
            author="F. Scott Fitzgerald",
            pub_date="1925",
            source_id="001",
            country_code="xxu",
            country_classification=CountryClassification.US,
        )

        # Create batch file
        batch_file = batch_dir / "batch_00001.pkl"
        with open(batch_file, "wb") as f:
            pickle.dump([marc_pub], f)

        # Create BatchProcessingInfo tuple
        batch_info = (
            1,  # batch_id
            str(batch_file),  # batch_path
            str(tmp_path / "cache"),  # cache_dir
            str(tmp_path / "copyright"),  # copyright_dir
            str(tmp_path / "renewal"),  # renewal_dir
            "test_hash",  # config_hash
            {"min_length": 10},  # detector_config
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
            1920,  # min_year
            1930,  # max_year
            str(result_dir),  # result_temp_dir
        )

        # Create a mock copyright publication that will match
        mock_copyright_pub = Publication(
            title="The Great Gatsby",
            author="Fitzgerald, F. Scott",
            publisher="Scribner",
            pub_date="1925",
            source_id="A00001",
        )

        # Create a mock matching engine that will return proper candidates
        DataMatcher()

        # Mock worker data with matches
        mock_reg_index = Mock()
        # Return the copyright publication when candidates are requested
        mock_reg_index.find_candidates = Mock(return_value=[0])  # Return index 0
        mock_reg_index.publications = [mock_copyright_pub]  # Store the publication at index 0

        # Import the module
        # Local imports
        import marc_pd_tool.application.processing.matching_engine

        with (
            patch.object(
                marc_pd_tool.application.processing.matching_engine,
                "_worker_registration_index",
                mock_reg_index,
            ),
            patch.object(
                marc_pd_tool.application.processing.matching_engine,
                "_worker_renewal_index",
                Mock(find_candidates=Mock(return_value=[]), publications=[]),
            ),
            patch.object(
                marc_pd_tool.application.processing.matching_engine,
                "_worker_generic_detector",
                Mock(is_generic=Mock(return_value=False)),
            ),
            patch.object(
                marc_pd_tool.application.processing.matching_engine, "_worker_config", None
            ),
        ):
            # Process batch
            batch_id, result_path, stats = process_batch(batch_info)

            assert batch_id == 1
            assert os.path.exists(result_path)
            assert stats.marc_count == 1
            assert stats.registration_matches_found == 1

            # Load and verify results
            with open(result_path, "rb") as f:
                results = pickle.load(f)

            assert len(results) == 1
            assert results[0].registration_match is not None

    def test_process_batch_with_pickle_error(self, tmp_path):
        """Test batch processing with pickle loading error"""
        # Create batch file with invalid pickle data
        batch_file = tmp_path / "bad_batch.pkl"
        with open(batch_file, "wb") as f:
            f.write(b"invalid pickle data")

        result_dir = tmp_path / "results"
        result_dir.mkdir()

        # Create BatchProcessingInfo tuple
        batch_info = (
            1,  # batch_id
            str(batch_file),  # batch_path
            str(tmp_path / "cache"),  # cache_dir
            str(tmp_path / "copyright"),  # copyright_dir
            str(tmp_path / "renewal"),  # renewal_dir
            "test_hash",  # config_hash
            {"min_length": 10},  # detector_config
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

        # Process batch - the function raises on pickle error
        # Import the module
        # Local imports
        import marc_pd_tool.application.processing.matching_engine

        with (
            patch.object(
                marc_pd_tool.application.processing.matching_engine,
                "_worker_registration_index",
                Mock(),
            ),
            patch.object(
                marc_pd_tool.application.processing.matching_engine, "_worker_renewal_index", Mock()
            ),
            patch.object(
                marc_pd_tool.application.processing.matching_engine,
                "_worker_generic_detector",
                Mock(),
            ),
            patch.object(
                marc_pd_tool.application.processing.matching_engine, "_worker_config", None
            ),
        ):
            # Expect the exception to be raised
            with pytest.raises(pickle.UnpicklingError):
                process_batch(batch_info)


class TestDataMatcherInternalMethods:
    """Test internal methods of DataMatcher"""

    def test_calculate_combined_score_no_author(self):
        """Test combined score calculation without author"""
        DataMatcher()

        marc_pub = Publication(
            title="Book Title",
            author="",  # Empty author
            publisher="Publisher",
            pub_date="1950",
            source_id="001",
        )

        copyright_pub = Publication(
            title="Book Title",
            author="",  # Empty author
            publisher="Publisher",
            pub_date="1950",
            source_id="c001",
        )

        # Use ScoreCombiner directly for testing score combination
        config = get_config()
        combiner = ScoreCombiner(config)
        score = combiner.combine_scores(
            title_score=90.0,
            author_score=0.0,
            publisher_score=80.0,
            has_generic_title=False,
            use_config_weights=True,
        )

        # Without author, weight should be redistributed
        assert score > 0

    def test_calculate_combined_score_only_title(self):
        """Test combined score with only title available"""
        DataMatcher()

        marc_pub = Publication(
            title="Book Title",
            author="",  # Empty author
            publisher="",  # Empty publisher
            pub_date="1950",
            source_id="001",
        )

        copyright_pub = Publication(title="Book Title", pub_date="1950", source_id="c001")

        # Use ScoreCombiner directly for testing score combination
        config = get_config()
        combiner = ScoreCombiner(config)
        score = combiner.combine_scores(
            title_score=85.0,
            author_score=0.0,
            publisher_score=0.0,
            has_generic_title=False,
            use_config_weights=True,
        )

        # With default weights (0.5/0.3/0.2) and normalization,
        # when only title has a score, the combined score is lower
        assert score == 49.58

    def test_find_best_match_no_matches_below_threshold(self):
        """Test find_best_match when all candidates are below threshold"""
        matcher = DataMatcher()

        marc_pub = Publication(
            title="Unique Book Title That Won't Match",
            author="Unknown Author",
            pub_date="1950",
            source_id="001",
        )

        copyright_pubs = [
            Publication(
                title="Completely Different Title",
                author="Different Author",
                pub_date="1950",
                source_id="c001",
            ),
            Publication(
                title="Another Different Title",
                author="Another Author",
                pub_date="1950",
                source_id="c002",
            ),
        ]

        result = matcher.find_best_match(
            marc_pub,
            copyright_pubs,
            year_tolerance=2,
            title_threshold=80,  # High threshold
            author_threshold=80,  # High threshold
            publisher_threshold=80,
            early_exit_title=95,
            early_exit_author=90,
            generic_detector=None,
        )

        # Should return None when no matches meet threshold
        assert result is None

    def test_find_best_match_with_abbreviated_author(self):
        """Test matching with abbreviated author names"""
        matcher = DataMatcher()

        marc_pub = Publication(
            title="Book Title",
            author="Smith, John",  # Full author name
            pub_date="1950",
            source_id="001",
        )

        copyright_pubs = [
            Publication(
                title="Book Title",
                author="Smith, J.",  # Abbreviated match
                pub_date="1950",
                source_id="c001",
            )
        ]

        result = matcher.find_best_match(
            marc_pub,
            copyright_pubs,
            year_tolerance=2,
            title_threshold=40,
            author_threshold=30,
            publisher_threshold=20,
            early_exit_title=95,
            early_exit_author=90,
            generic_detector=None,
        )

        # Should find match even with abbreviated author
        assert result is not None
        assert result["copyright_record"]["source_id"] == "c001"
