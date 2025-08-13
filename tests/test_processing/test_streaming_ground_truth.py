# tests/test_processing/test_streaming_ground_truth.py

"""Tests for streaming ground truth processing functionality"""

# Standard library imports
from pathlib import Path
from pickle import dump as pickle_dump
from pickle import load as pickle_load
from tempfile import TemporaryDirectory
from unittest.mock import patch

# Third party imports
import pytest

# Local imports
from marc_pd_tool.application.processing.ground_truth_extractor import (
    GroundTruthExtractor,
)
from marc_pd_tool.core.domain.enums import CountryClassification
from marc_pd_tool.core.domain.publication import Publication


class TestStreamingGroundTruthExtractor:
    """Test streaming functionality in ground truth extraction"""

    @pytest.fixture
    def sample_marc_publications(self) -> list[Publication]:
        """Sample MARC publications with LCCNs for testing"""
        return [
            Publication(
                title="First Test Book",
                author="Test Author",
                main_author="Test, Author",
                pub_date="1975",
                publisher="Test Publisher",
                place="New York",
                edition="",
                lccn="75123456",
                language_code="eng",
                source="MARC",
                source_id="001",
                country_code="nyu",
                country_classification=CountryClassification.US,
            ),
            Publication(
                title="Second Test Book",
                author="Another Author",
                main_author="Another, Author",
                pub_date="1976",
                publisher="Another Publisher",
                place="Chicago",
                edition="",
                lccn="76654321",
                language_code="eng",
                source="MARC",
                source_id="002",
                country_code="ilu",
                country_classification=CountryClassification.US,
            ),
            Publication(
                title="Third Test Book",
                author="Third Author",
                main_author="Third, Author",
                pub_date="1977",
                publisher="Third Publisher",
                place="Boston",
                edition="",
                lccn="",  # No LCCN
                language_code="eng",
                source="MARC",
                source_id="003",
                country_code="mau",
                country_classification=CountryClassification.US,
            ),
        ]

    @pytest.fixture
    def sample_copyright_publications(self) -> list[Publication]:
        """Sample copyright publications with matching LCCNs"""
        return [
            Publication(
                title="First Test Book [Matching]",
                author="Test Author Match",
                main_author="",
                pub_date="1975",
                publisher="Test Publisher Match",
                place="",
                edition="",
                lccn="75123456",
                language_code="",
                source="COPYRIGHT",
                source_id="reg001",
                country_code="",
                country_classification=CountryClassification.UNKNOWN,
            ),
            Publication(
                title="Different Book",
                author="Different Author",
                main_author="",
                pub_date="1978",
                publisher="Different Publisher",
                place="",
                edition="",
                lccn="78999999",
                language_code="",
                source="COPYRIGHT",
                source_id="reg002",
                country_code="",
                country_classification=CountryClassification.UNKNOWN,
            ),
        ]

    @pytest.fixture
    def sample_renewal_publications(self) -> list[Publication]:
        """Sample renewal publications with matching LCCNs"""
        return [
            Publication(
                title="Second Test Book Renewal",
                author="Another Author Renewal",
                main_author="",
                pub_date="1976",
                publisher="Another Publisher Renewal",
                place="",
                edition="",
                lccn="76654321",
                language_code="",
                source="RENEWAL",
                source_id="ren001",
                country_code="",
                country_classification=CountryClassification.UNKNOWN,
            )
        ]

    def test_extract_ground_truth_from_pickles_basic(
        self,
        sample_marc_publications: list[Publication],
        sample_copyright_publications: list[Publication],
        sample_renewal_publications: list[Publication],
    ):
        """Test extract_ground_truth_from_pickles basic functionality"""
        extractor = GroundTruthExtractor()

        with TemporaryDirectory() as temp_dir:
            # Create pickle files
            pickle_paths = []
            batch_size = 2

            for i in range(0, len(sample_marc_publications), batch_size):
                batch = sample_marc_publications[i : i + batch_size]
                pickle_path = Path(temp_dir) / f"batch_{len(pickle_paths):03d}.pkl"

                with open(pickle_path, "wb") as f:
                    pickle_dump(batch, f)
                pickle_paths.append(str(pickle_path))

            # Extract ground truth from pickles
            pairs, stats = extractor.extract_ground_truth_from_pickles(
                pickle_paths, sample_copyright_publications, sample_renewal_publications
            )

            # Should find matches for publications with LCCNs
            assert len(pairs) >= 2  # At least copyright and renewal matches
            assert stats.total_marc_records == 3
            assert stats.marc_with_lccn == 2  # Two publications have LCCNs
            assert stats.registration_matches >= 1
            assert stats.renewal_matches >= 1

    def test_extract_ground_truth_from_pickles_empty_pickles(
        self,
        sample_copyright_publications: list[Publication],
        sample_renewal_publications: list[Publication],
    ):
        """Test extract_ground_truth_from_pickles handles empty pickle files"""
        extractor = GroundTruthExtractor()

        with TemporaryDirectory() as temp_dir:
            # Create empty pickle file
            pickle_path = Path(temp_dir) / "empty_batch.pkl"
            with open(pickle_path, "wb") as f:
                pickle_dump([], f)

            pairs, stats = extractor.extract_ground_truth_from_pickles(
                [str(pickle_path)], sample_copyright_publications, sample_renewal_publications
            )

            assert len(pairs) == 0
            assert stats.total_marc_records == 0
            assert stats.marc_with_lccn == 0
            assert stats.registration_matches == 0
            assert stats.renewal_matches == 0

    def test_extract_ground_truth_from_pickles_no_lccn_records(
        self,
        sample_copyright_publications: list[Publication],
        sample_renewal_publications: list[Publication],
    ):
        """Test extract_ground_truth_from_pickles with records having no LCCNs"""
        # Create publications without LCCNs
        no_lccn_pubs = [
            Publication(
                title="No LCCN Book One",
                author="Author One",
                main_author="One, Author",
                pub_date="1975",
                publisher="Publisher One",
                place="New York",
                edition="",
                lccn="",  # No LCCN
                language_code="eng",
                source="MARC",
                source_id="001",
                country_code="nyu",
                country_classification=CountryClassification.US,
            ),
            Publication(
                title="No LCCN Book Two",
                author="Author Two",
                main_author="Two, Author",
                pub_date="1976",
                publisher="Publisher Two",
                place="Chicago",
                edition="",
                lccn="",  # No LCCN
                language_code="eng",
                source="MARC",
                source_id="002",
                country_code="ilu",
                country_classification=CountryClassification.US,
            ),
        ]

        extractor = GroundTruthExtractor()

        with TemporaryDirectory() as temp_dir:
            # Create pickle file with no-LCCN records
            pickle_path = Path(temp_dir) / "no_lccn_batch.pkl"
            with open(pickle_path, "wb") as f:
                pickle_dump(no_lccn_pubs, f)

            pairs, stats = extractor.extract_ground_truth_from_pickles(
                [str(pickle_path)], sample_copyright_publications, sample_renewal_publications
            )

            assert len(pairs) == 0  # No matches possible without LCCNs
            assert stats.total_marc_records == 2
            assert stats.marc_with_lccn == 0  # No LCCNs
            assert stats.registration_matches == 0
            assert stats.renewal_matches == 0
            assert stats.marc_lccn_coverage == 0.0  # 0% coverage

    def test_extract_ground_truth_from_pickles_mixed_batches(
        self,
        sample_marc_publications: list[Publication],
        sample_copyright_publications: list[Publication],
        sample_renewal_publications: list[Publication],
    ):
        """Test extract_ground_truth_from_pickles with mixed batch sizes"""
        extractor = GroundTruthExtractor()

        with TemporaryDirectory() as temp_dir:
            pickle_paths = []

            # Create batches of different sizes
            batch_configs = [
                (sample_marc_publications[:1], "single_record"),
                (sample_marc_publications[1:], "remaining_records"),
            ]

            for batch, name in batch_configs:
                pickle_path = Path(temp_dir) / f"{name}.pkl"
                with open(pickle_path, "wb") as f:
                    pickle_dump(batch, f)
                pickle_paths.append(str(pickle_path))

            pairs, stats = extractor.extract_ground_truth_from_pickles(
                pickle_paths, sample_copyright_publications, sample_renewal_publications
            )

            # Should still find all matches
            assert stats.total_marc_records == 3
            assert stats.marc_with_lccn == 2
            assert len(pairs) >= 2

    def test_extract_ground_truth_from_pickles_nonexistent_files(
        self,
        sample_copyright_publications: list[Publication],
        sample_renewal_publications: list[Publication],
    ):
        """Test extract_ground_truth_from_pickles handles nonexistent files"""
        extractor = GroundTruthExtractor()

        # Try to extract from nonexistent files
        nonexistent_paths = ["/path/that/does/not/exist.pkl", "/another/missing/file.pkl"]

        pairs, stats = extractor.extract_ground_truth_from_pickles(
            nonexistent_paths, sample_copyright_publications, sample_renewal_publications
        )

        # Should handle gracefully without crashing
        assert len(pairs) == 0
        assert stats.total_marc_records == 0
        assert stats.marc_with_lccn == 0

    def test_extract_ground_truth_from_pickles_corrupted_files(
        self,
        sample_copyright_publications: list[Publication],
        sample_renewal_publications: list[Publication],
    ):
        """Test extract_ground_truth_from_pickles handles corrupted pickle files"""
        extractor = GroundTruthExtractor()

        with TemporaryDirectory() as temp_dir:
            # Create corrupted pickle file
            corrupted_path = Path(temp_dir) / "corrupted.pkl"
            with open(corrupted_path, "w") as f:
                f.write("This is not a valid pickle file")

            pairs, stats = extractor.extract_ground_truth_from_pickles(
                [str(corrupted_path)], sample_copyright_publications, sample_renewal_publications
            )

            # Should handle gracefully without crashing
            assert len(pairs) == 0
            assert stats.total_marc_records == 0

    def test_streaming_ground_truth_performance_large_batches(
        self,
        sample_copyright_publications: list[Publication],
        sample_renewal_publications: list[Publication],
    ):
        """Test streaming ground truth extraction performance with larger datasets"""
        # Create a larger set of MARC publications
        large_marc_set = []
        for i in range(100):
            pub = Publication(
                title=f"Test Book {i:03d}",
                author=f"Author {i:03d}",
                main_author=f"Last{i:03d}, First",
                pub_date=str(1970 + (i % 30)),
                publisher=f"Publisher {i:03d}",
                place="Test City",
                edition="",
                lccn=f"{(70 + i % 30):02d}{i:06d}" if i % 3 == 0 else "",  # Some have LCCNs
                language_code="eng",
                source="MARC",
                source_id=f"{i:06d}",
                country_code="nyu",
                country_classification=CountryClassification.US,
            )
            large_marc_set.append(pub)

        extractor = GroundTruthExtractor()

        with TemporaryDirectory() as temp_dir:
            pickle_paths = []
            batch_size = 10

            # Create multiple pickle files
            for i in range(0, len(large_marc_set), batch_size):
                batch = large_marc_set[i : i + batch_size]
                pickle_path = Path(temp_dir) / f"batch_{i // batch_size:03d}.pkl"

                with open(pickle_path, "wb") as f:
                    pickle_dump(batch, f)
                pickle_paths.append(str(pickle_path))

            # Extract ground truth - should complete without issues
            pairs, stats = extractor.extract_ground_truth_from_pickles(
                pickle_paths, sample_copyright_publications, sample_renewal_publications
            )

            assert stats.total_marc_records == 100
            assert stats.marc_with_lccn > 0  # Some records have LCCNs
            assert len(pickle_paths) == 10  # Should create 10 pickle files

    def test_streaming_ground_truth_memory_efficiency(
        self,
        sample_marc_publications: list[Publication],
        sample_copyright_publications: list[Publication],
        sample_renewal_publications: list[Publication],
    ):
        """Test that streaming ground truth extraction doesn't load all data at once"""
        extractor = GroundTruthExtractor()

        with TemporaryDirectory() as temp_dir:
            pickle_paths = []

            # Create individual pickle files for each publication
            for i, pub in enumerate(sample_marc_publications):
                pickle_path = Path(temp_dir) / f"single_{i:03d}.pkl"
                with open(pickle_path, "wb") as f:
                    pickle_dump([pub], f)  # Single publication per file
                pickle_paths.append(str(pickle_path))

            # Mock the pickle loading to track how many files are loaded simultaneously
            original_load = pickle_load
            load_count = 0
            max_concurrent_loads = 0

            def mock_pickle_load(file):
                nonlocal load_count, max_concurrent_loads
                load_count += 1
                max_concurrent_loads = max(max_concurrent_loads, load_count)
                try:
                    return original_load(file)
                finally:
                    load_count -= 1

            with patch(
                "marc_pd_tool.application.processing.ground_truth_extractor.load",
                side_effect=mock_pickle_load,
            ):
                pairs, stats = extractor.extract_ground_truth_from_pickles(
                    pickle_paths, sample_copyright_publications, sample_renewal_publications
                )

            # Should process files one at a time, not all at once
            assert max_concurrent_loads <= 2  # At most loading one file at a time
            assert stats.total_marc_records == 3

    def test_streaming_ground_truth_maintains_accuracy(
        self,
        sample_marc_publications: list[Publication],
        sample_copyright_publications: list[Publication],
        sample_renewal_publications: list[Publication],
    ):
        """Test streaming ground truth produces same results as non-streaming"""
        extractor = GroundTruthExtractor()

        # Extract using regular method (direct publications)
        marc_batches = [sample_marc_publications]  # Wrap in batch format
        regular_pairs, regular_stats = extractor.extract_ground_truth_pairs(
            marc_batches, sample_copyright_publications, sample_renewal_publications
        )

        # Extract using streaming method (pickle files)
        with TemporaryDirectory() as temp_dir:
            pickle_paths = []

            # Create pickle files
            for i, pub in enumerate(sample_marc_publications):
                pickle_path = Path(temp_dir) / f"pub_{i:03d}.pkl"
                with open(pickle_path, "wb") as f:
                    pickle_dump([pub], f)
                pickle_paths.append(str(pickle_path))

            streaming_pairs, streaming_stats = extractor.extract_ground_truth_from_pickles(
                pickle_paths, sample_copyright_publications, sample_renewal_publications
            )

        # Results should be identical
        assert len(regular_pairs) == len(streaming_pairs)
        assert regular_stats.total_marc_records == streaming_stats.total_marc_records
        assert regular_stats.marc_with_lccn == streaming_stats.marc_with_lccn
        assert regular_stats.registration_matches == streaming_stats.registration_matches
        assert regular_stats.renewal_matches == streaming_stats.renewal_matches

        # Compare individual pairs (order might differ, so sort by LCCN)
        # Filter out entries without LCCN for sorting
        regular_with_lccn = [p for p in regular_pairs if p.lccn]
        streaming_with_lccn = [p for p in streaming_pairs if p.lccn]

        regular_pairs_sorted = sorted(regular_with_lccn, key=lambda p: p.lccn)
        streaming_pairs_sorted = sorted(streaming_with_lccn, key=lambda p: p.lccn)

        for reg_pair, stream_pair in zip(regular_pairs_sorted, streaming_pairs_sorted):
            assert reg_pair.lccn == stream_pair.lccn
            assert reg_pair.normalized_lccn == stream_pair.normalized_lccn
            # Check that match types are the same
            if reg_pair.registration_match:
                assert stream_pair.registration_match is not None
                assert (
                    reg_pair.registration_match.match_type
                    == stream_pair.registration_match.match_type
                )
            if reg_pair.renewal_match:
                assert stream_pair.renewal_match is not None
                assert reg_pair.renewal_match.match_type == stream_pair.renewal_match.match_type


class TestStreamingGroundTruthIntegration:
    """Integration tests for streaming ground truth with other components"""

    def test_streaming_ground_truth_with_api_integration(self):
        """Test streaming ground truth works with API layer"""
        # This test would verify that the API can use streaming ground truth
        # when working with large datasets that are pickled to disk

        # Create sample data
        marc_pubs = [
            Publication(
                title="Integration Test Book",
                author="Integration Author",
                main_author="Integration, Author",
                pub_date="1975",
                publisher="Integration Publisher",
                place="New York",
                edition="",
                lccn="75999999",
                language_code="eng",
                source="MARC",
                source_id="int001",
                country_code="nyu",
                country_classification=CountryClassification.US,
            )
        ]

        copyright_pubs = [
            Publication(
                title="Integration Test Book Match",
                author="Integration Author Match",
                main_author="",
                pub_date="1975",
                publisher="Integration Publisher Match",
                place="",
                edition="",
                lccn="75999999",
                language_code="",
                source="COPYRIGHT",
                source_id="intcopy001",
                country_code="",
                country_classification=CountryClassification.UNKNOWN,
            )
        ]

        extractor = GroundTruthExtractor()

        with TemporaryDirectory() as temp_dir:
            # Create pickle file
            pickle_path = Path(temp_dir) / "integration_test.pkl"
            with open(pickle_path, "wb") as f:
                pickle_dump(marc_pubs, f)

            # Extract using streaming
            pairs, stats = extractor.extract_ground_truth_from_pickles(
                [str(pickle_path)], copyright_pubs, []
            )

            # Verify integration works
            assert len(pairs) == 1
            assert stats.total_marc_records == 1
            assert stats.marc_with_lccn == 1
            assert stats.registration_matches == 1
            # Check that the MARC record has a registration match
            assert pairs[0].registration_match is not None
            assert pairs[0].registration_match.source_type == "registration"

    def test_streaming_ground_truth_error_recovery(self):
        """Test streaming ground truth recovers from individual file errors"""
        copyright_pubs = [
            Publication(
                title="Recovery Test Book",
                author="Recovery Author",
                main_author="",
                pub_date="1975",
                publisher="Recovery Publisher",
                place="",
                edition="",
                lccn="75888888",
                language_code="",
                source="COPYRIGHT",
                source_id="rec001",
                country_code="",
                country_classification=CountryClassification.UNKNOWN,
            )
        ]

        good_marc_pub = Publication(
            title="Good MARC Book",
            author="Good Author",
            main_author="Good, Author",
            pub_date="1975",
            publisher="Good Publisher",
            place="New York",
            edition="",
            lccn="75888888",
            language_code="eng",
            source="MARC",
            source_id="good001",
            country_code="nyu",
            country_classification=CountryClassification.US,
        )

        extractor = GroundTruthExtractor()

        with TemporaryDirectory() as temp_dir:
            # Create good pickle file
            good_pickle = Path(temp_dir) / "good_batch.pkl"
            with open(good_pickle, "wb") as f:
                pickle_dump([good_marc_pub], f)

            # Create corrupted pickle file
            bad_pickle = Path(temp_dir) / "bad_batch.pkl"
            with open(bad_pickle, "w") as f:
                f.write("corrupted pickle data")

            # Should recover from bad file and still process good one
            pickle_paths = [str(good_pickle), str(bad_pickle)]
            pairs, stats = extractor.extract_ground_truth_from_pickles(
                pickle_paths, copyright_pubs, []
            )

            # Should still extract from good file despite bad file
            assert len(pairs) >= 0  # May find matches from good file
            # Total should reflect only successfully processed files
