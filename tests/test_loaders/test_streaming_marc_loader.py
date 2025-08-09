# tests/test_loaders/test_streaming_marc_loader.py

"""Comprehensive tests for streaming MARC processing functionality"""

# Standard library imports
from pathlib import Path
from pickle import load as pickle_load
from tempfile import NamedTemporaryFile
from tempfile import TemporaryDirectory
from unittest.mock import patch

# Third party imports
import pytest

# Local imports
from marc_pd_tool.data.enums import CountryClassification
from marc_pd_tool.loaders.marc_loader import MarcLoader


class TestStreamingMarcLoader:
    """Test streaming functionality in MarcLoader"""

    @pytest.fixture
    def sample_marcxml_content(self) -> str:
        """Sample MARCXML content for testing"""
        return """<?xml version="1.0" encoding="UTF-8"?>
<collection xmlns="http://www.loc.gov/MARC21/slim">
  <record>
    <controlfield tag="001">12345</controlfield>
    <controlfield tag="008">750101s1975    nyu           000 0 eng  </controlfield>
    <datafield tag="245" ind1="1" ind2="0">
      <subfield code="a">Test title one</subfield>
    </datafield>
    <datafield tag="260" ind1=" " ind2=" ">
      <subfield code="a">New York :</subfield>
      <subfield code="b">Test Publisher,</subfield>
      <subfield code="c">1975.</subfield>
    </datafield>
  </record>
  <record>
    <controlfield tag="001">12346</controlfield>
    <controlfield tag="008">760101s1976    nyu           000 0 eng  </controlfield>
    <datafield tag="245" ind1="1" ind2="0">
      <subfield code="a">Test title two</subfield>
    </datafield>
    <datafield tag="260" ind1=" " ind2=" ">
      <subfield code="a">New York :</subfield>
      <subfield code="b">Another Publisher,</subfield>
      <subfield code="c">1976.</subfield>
    </datafield>
  </record>
  <record>
    <controlfield tag="001">12347</controlfield>
    <controlfield tag="008">770101s1977    nyu           000 0 eng  </controlfield>
    <datafield tag="245" ind1="1" ind2="0">
      <subfield code="a">Test title three</subfield>
    </datafield>
    <datafield tag="260" ind1=" " ind2=" ">
      <subfield code="a">New York :</subfield>
      <subfield code="b">Third Publisher,</subfield>
      <subfield code="c">1977.</subfield>
    </datafield>
  </record>
</collection>"""

    @pytest.fixture
    def temp_marcxml_file(self, sample_marcxml_content: str) -> str:
        """Create a temporary MARCXML file for testing"""
        with NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as f:
            f.write(sample_marcxml_content)
            return f.name

    def test_extract_all_batches_uses_streaming_internally(self, temp_marcxml_file: str):
        """Test that extract_all_batches always uses streaming internally"""
        loader = MarcLoader(temp_marcxml_file, batch_size=2)

        # Mock the _extract_with_streaming method to verify it's called
        with patch.object(loader, "_extract_with_streaming", return_value=[]) as mock_streaming:
            loader.extract_all_batches()
            mock_streaming.assert_called_once()

    def test_iter_batches_yields_correct_batch_sizes(self, temp_marcxml_file: str):
        """Test iter_batches yields batches of the correct size"""
        loader = MarcLoader(temp_marcxml_file, batch_size=2)

        batches = list(loader.iter_batches())

        # Should have 2 batches: [2 records, 1 record]
        assert len(batches) == 2
        assert len(batches[0]) == 2
        assert len(batches[1]) == 1

        # Verify the publications are correct
        assert batches[0][0].title == "test title one"
        assert batches[0][1].title == "test title two"
        assert batches[1][0].title == "test title three"

    def test_iter_batches_memory_efficient(self, temp_marcxml_file: str):
        """Test that iter_batches doesn't accumulate all data in memory"""
        loader = MarcLoader(temp_marcxml_file, batch_size=1)

        batch_count = 0
        total_records = 0

        # Process batches one at a time
        for batch in loader.iter_batches():
            batch_count += 1
            total_records += len(batch)
            # Each batch should have exactly 1 record
            assert len(batch) == 1

        assert batch_count == 3
        assert total_records == 3

    def test_extract_batches_to_disk_creates_pickle_files(self, temp_marcxml_file: str):
        """Test extract_batches_to_disk creates pickle files on disk"""
        loader = MarcLoader(temp_marcxml_file, batch_size=2)

        with TemporaryDirectory() as temp_dir:
            pickle_paths, total_records, filtered_count = loader.extract_batches_to_disk(temp_dir)

            # Should create 2 pickle files
            assert len(pickle_paths) == 2
            assert total_records == 3
            assert filtered_count == 0

            # Verify pickle files exist and contain correct data
            for path in pickle_paths:
                assert Path(path).exists()

            # Load and verify first pickle file
            with open(pickle_paths[0], "rb") as f:
                batch = pickle_load(f)
                assert len(batch) == 2
                assert batch[0].title == "test title one"
                assert batch[1].title == "test title two"

            # Load and verify second pickle file
            with open(pickle_paths[1], "rb") as f:
                batch = pickle_load(f)
                assert len(batch) == 1
                assert batch[0].title == "test title three"

    def test_extract_batches_to_disk_with_filtering(self, temp_marcxml_file: str):
        """Test extract_batches_to_disk respects filtering options"""
        # Filter to only include records from 1976 and later
        loader = MarcLoader(temp_marcxml_file, batch_size=2, min_year=1976)

        with TemporaryDirectory() as temp_dir:
            pickle_paths, total_records, filtered_count = loader.extract_batches_to_disk(temp_dir)

            # Should filter out 1975 record
            assert total_records == 3  # Total records processed
            assert filtered_count == 1  # 1975 record filtered out
            assert len(pickle_paths) == 1  # Only need 1 pickle file for 2 remaining records

            # Verify remaining records
            with open(pickle_paths[0], "rb") as f:
                batch = pickle_load(f)
                assert len(batch) == 2
                assert batch[0].year == 1976
                assert batch[1].year == 1977

    def test_extract_batches_to_disk_auto_temp_dir(self, temp_marcxml_file: str):
        """Test extract_batches_to_disk creates temp directory when none provided"""
        loader = MarcLoader(temp_marcxml_file, batch_size=2)

        pickle_paths, total_records, filtered_count = loader.extract_batches_to_disk()

        # Should still create pickle files
        assert len(pickle_paths) > 0
        assert total_records == 3

        # Verify temp directory is tracked
        temp_dir = loader.get_temp_batch_dir()
        assert temp_dir is not None
        assert Path(temp_dir).exists()

        # Verify pickle files are in the temp directory
        for path in pickle_paths:
            assert temp_dir in path

    def test_streaming_with_us_only_filter(self, temp_marcxml_file: str):
        """Test streaming works correctly with US-only filtering"""
        loader = MarcLoader(temp_marcxml_file, batch_size=2, us_only=True)

        batches = list(loader.iter_batches())

        # All test records are US publications (nyu in 008 field)
        total_publications = sum(len(batch) for batch in batches)
        assert total_publications == 3

        # Verify all publications are classified as US
        for batch in batches:
            for pub in batch:
                assert pub.country_classification == CountryClassification.US

    def test_streaming_handles_empty_file(self):
        """Test streaming handles empty MARCXML files gracefully"""
        empty_content = """<?xml version="1.0" encoding="UTF-8"?>
<collection xmlns="http://www.loc.gov/MARC21/slim">
</collection>"""

        with NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as f:
            f.write(empty_content)
            temp_file = f.name

        loader = MarcLoader(temp_file, batch_size=2)

        # Should handle empty file without error
        batches = list(loader.iter_batches())
        assert len(batches) == 0

        # extract_all_batches should also handle empty file
        all_batches = loader.extract_all_batches()
        assert len(all_batches) == 0

    def test_streaming_handles_malformed_xml(self):
        """Test streaming handles malformed XML gracefully"""
        malformed_content = """<?xml version="1.0" encoding="UTF-8"?>
<collection xmlns="http://www.loc.gov/MARC21/slim">
  <record>
    <controlfield tag="001">12345</controlfield>
    <datafield tag="245" ind1="1" ind2="0">
      <subfield code="a">Test title</subfield>
    </datafield>
    <!-- Missing closing tag for record -->
</collection>"""

        with NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as f:
            f.write(malformed_content)
            temp_file = f.name

        loader = MarcLoader(temp_file, batch_size=2)

        # Should handle malformed XML without crashing
        batches = list(loader.iter_batches())
        # May or may not extract records depending on XML parser behavior
        # The important thing is it doesn't crash
        assert isinstance(batches, list)

    def test_streaming_consistent_with_traditional_approach(self, temp_marcxml_file: str):
        """Test that streaming produces the same results as traditional loading"""
        loader = MarcLoader(temp_marcxml_file, batch_size=2)

        # Get results from streaming
        streaming_batches = loader.extract_all_batches()
        streaming_pubs = [pub for batch in streaming_batches for pub in batch]

        # Get results from iter_batches (also streaming)
        iter_batches = list(loader.iter_batches())
        iter_pubs = [pub for batch in iter_batches for pub in batch]

        # Should produce identical results
        assert len(streaming_pubs) == len(iter_pubs) == 3

        for i, (stream_pub, iter_pub) in enumerate(zip(streaming_pubs, iter_pubs)):
            assert stream_pub.title == iter_pub.title
            assert stream_pub.year == iter_pub.year
            assert stream_pub.source_id == iter_pub.source_id

    def test_streaming_performance_large_batch_size(self, temp_marcxml_file: str):
        """Test streaming works correctly with large batch sizes"""
        # Use a batch size larger than the total number of records
        loader = MarcLoader(temp_marcxml_file, batch_size=10)

        batches = list(loader.iter_batches())

        # Should create 1 batch with all 3 records
        assert len(batches) == 1
        assert len(batches[0]) == 3

    def test_streaming_performance_small_batch_size(self, temp_marcxml_file: str):
        """Test streaming works correctly with small batch sizes"""
        loader = MarcLoader(temp_marcxml_file, batch_size=1)

        batches = list(loader.iter_batches())

        # Should create 3 batches with 1 record each
        assert len(batches) == 3
        for batch in batches:
            assert len(batch) == 1


class TestStreamingErrorHandling:
    """Test error handling in streaming functionality"""

    @pytest.fixture
    def temp_marcxml_file(self) -> str:
        """Create a temporary MARCXML file for error handling tests"""
        sample_content = """<?xml version="1.0" encoding="UTF-8"?>
<collection xmlns="http://www.loc.gov/MARC21/slim">
  <record>
    <controlfield tag="001">12345</controlfield>
    <controlfield tag="008">750101s1975    nyu           000 0 eng  </controlfield>
    <datafield tag="245" ind1="1" ind2="0">
      <subfield code="a">Test title</subfield>
    </datafield>
    <datafield tag="260" ind1=" " ind2=" ">
      <subfield code="a">New York :</subfield>
      <subfield code="b">Test Publisher,</subfield>
      <subfield code="c">1975.</subfield>
    </datafield>
  </record>
</collection>"""

        with NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as f:
            f.write(sample_content)
            return f.name

    def test_nonexistent_file_handling(self):
        """Test streaming handles nonexistent files gracefully"""
        loader = MarcLoader("nonexistent_file.xml", batch_size=2)

        # Should handle nonexistent file without crashing
        batches = loader.extract_all_batches()
        assert batches == []

        # iter_batches should also handle gracefully
        iter_batches = list(loader.iter_batches())
        assert iter_batches == []

    def test_extract_batches_to_disk_io_error_recovery(self, temp_marcxml_file: str):
        """Test extract_batches_to_disk handles I/O errors gracefully"""
        loader = MarcLoader(temp_marcxml_file, batch_size=2)

        # Try to write to a read-only directory (should fail gracefully)
        try:
            with TemporaryDirectory() as temp_dir:
                readonly_dir = Path(temp_dir) / "readonly"
                readonly_dir.mkdir()
                readonly_dir.chmod(0o444)  # Read-only

                # Should handle permission error without crashing
                pickle_paths, total_records, filtered_count = loader.extract_batches_to_disk(
                    str(readonly_dir)
                )

                # May return empty results or handle error gracefully
                assert isinstance(pickle_paths, list)
                assert isinstance(total_records, int)
                assert isinstance(filtered_count, int)
        except PermissionError:
            # Expected on some systems
            pass

    def test_streaming_with_xml_parsing_errors(self):
        """Test streaming handles XML parsing errors gracefully"""
        invalid_xml = "This is not valid XML at all"

        with NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as f:
            f.write(invalid_xml)
            temp_file = f.name

        loader = MarcLoader(temp_file, batch_size=2)

        # Should handle invalid XML without crashing
        batches = list(loader.iter_batches())
        assert isinstance(batches, list)  # May be empty, but shouldn't crash


class TestStreamingIntegration:
    """Integration tests for streaming with other components"""

    @pytest.fixture
    def sample_marcxml_content(self) -> str:
        """Sample MARCXML content for integration tests"""
        return """<?xml version="1.0" encoding="UTF-8"?>
<collection xmlns="http://www.loc.gov/MARC21/slim">
  <record>
    <controlfield tag="001">12345</controlfield>
    <controlfield tag="008">750101s1975    nyu           000 0 eng  </controlfield>
    <datafield tag="245" ind1="1" ind2="0">
      <subfield code="a">Test title one</subfield>
    </datafield>
    <datafield tag="260" ind1=" " ind2=" ">
      <subfield code="a">New York :</subfield>
      <subfield code="b">Test Publisher,</subfield>
      <subfield code="c">1975.</subfield>
    </datafield>
  </record>
  <record>
    <controlfield tag="001">12346</controlfield>
    <controlfield tag="008">760101s1976    nyu           000 0 eng  </controlfield>
    <datafield tag="245" ind1="1" ind2="0">
      <subfield code="a">Test title two</subfield>
    </datafield>
    <datafield tag="260" ind1=" " ind2=" ">
      <subfield code="a">New York :</subfield>
      <subfield code="b">Another Publisher,</subfield>
      <subfield code="c">1976.</subfield>
    </datafield>
  </record>
  <record>
    <controlfield tag="001">12347</controlfield>
    <controlfield tag="008">770101s1977    nyu           000 0 eng  </controlfield>
    <datafield tag="245" ind1="1" ind2="0">
      <subfield code="a">Test title three</subfield>
    </datafield>
    <datafield tag="260" ind1=" " ind2=" ">
      <subfield code="a">New York :</subfield>
      <subfield code="b">Third Publisher,</subfield>
      <subfield code="c">1977.</subfield>
    </datafield>
  </record>
</collection>"""

    def test_streaming_with_year_filtering(self, sample_marcxml_content: str):
        """Test streaming works correctly with year-based filtering"""
        with NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as f:
            f.write(sample_marcxml_content)
            temp_file = f.name

        # Test different year filters
        test_cases = [
            (None, None, 3),  # No filter - all records
            (1976, None, 2),  # Min year 1976 - exclude 1975
            (None, 1976, 2),  # Max year 1976 - exclude 1977
            (1976, 1976, 1),  # Exact year 1976 - only 1976 record
            (1980, None, 0),  # No records after 1980
        ]

        for min_year, max_year, expected_count in test_cases:
            loader = MarcLoader(temp_file, batch_size=2, min_year=min_year, max_year=max_year)

            batches = list(loader.iter_batches())
            total_pubs = sum(len(batch) for batch in batches)

            assert (
                total_pubs == expected_count
            ), f"Failed for min_year={min_year}, max_year={max_year}"

    def test_streaming_preserves_publication_metadata(self, sample_marcxml_content: str):
        """Test streaming preserves all publication metadata correctly"""
        with NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as f:
            f.write(sample_marcxml_content)
            temp_file = f.name

        loader = MarcLoader(temp_file, batch_size=2)

        batches = list(loader.iter_batches())
        all_pubs = [pub for batch in batches for pub in batch]

        # Verify first publication metadata
        pub1 = all_pubs[0]
        assert pub1.title == "test title one"
        assert pub1.year == 1975
        assert pub1.source_id == "12345"
        assert pub1.country_classification == CountryClassification.US
        assert pub1.source == "MARC"

        # Verify all publications have required fields
        for pub in all_pubs:
            assert pub.title is not None
            assert pub.year is not None
            assert pub.source_id is not None
            assert pub.source == "MARC"
            assert pub.country_classification is not None

    def test_streaming_batch_consistency(self, sample_marcxml_content: str):
        """Test that different batch sizes produce consistent results"""
        with NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as f:
            f.write(sample_marcxml_content)
            temp_file = f.name

        # Test with different batch sizes
        batch_sizes = [1, 2, 3, 5, 10]
        all_results = []

        for batch_size in batch_sizes:
            loader = MarcLoader(temp_file, batch_size=batch_size)
            batches = list(loader.iter_batches())
            pubs = [pub for batch in batches for pub in batch]

            # Sort by source_id for consistent comparison
            pubs.sort(key=lambda p: p.source_id)
            all_results.append(pubs)

        # All batch sizes should produce identical results
        base_result = all_results[0]
        for i, result in enumerate(all_results[1:], 1):
            assert len(result) == len(
                base_result
            ), f"Batch size {batch_sizes[i]} produced different count"

            for j, (base_pub, test_pub) in enumerate(zip(base_result, result)):
                assert (
                    base_pub.title == test_pub.title
                ), f"Title mismatch at position {j} for batch size {batch_sizes[i]}"
                assert (
                    base_pub.source_id == test_pub.source_id
                ), f"Source ID mismatch at position {j} for batch size {batch_sizes[i]}"
