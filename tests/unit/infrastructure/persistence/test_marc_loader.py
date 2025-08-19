# tests/unit/infrastructure/persistence/test_marc_loader.py

"""Comprehensive tests for MarcLoader functionality - consolidates all MARC loading tests"""

# Standard library imports
from argparse import ArgumentParser
from pathlib import Path
from pickle import load as pickle_load
from tempfile import NamedTemporaryFile
from tempfile import TemporaryDirectory
from unittest.mock import patch
from xml.etree.ElementTree import Element
from xml.etree.ElementTree import SubElement
from xml.etree.ElementTree import fromstring
from xml.etree.ElementTree import tostring

# Third party imports
from pytest import fixture

# Local imports
from marc_pd_tool.core.domain.enums import CountryClassification
from marc_pd_tool.core.domain.publication import Publication
from marc_pd_tool.infrastructure.persistence import MarcLoader

# =============================================================================
# FILE HANDLING AND DISCOVERY TESTS
# =============================================================================


class TestMarcLoaderFileHandling:
    """Test file discovery and handling in MarcLoader"""

    def test_extract_all_batches_nonexistent_path(self):
        """Test handling of non-existent MARC path"""
        loader = MarcLoader("/nonexistent/path.xml")

        batches = loader.extract_all_batches()

        # Should return empty list
        assert batches == []

    def test_get_marc_files_single_file(self, tmp_path):
        """Test _get_marc_files with single XML file"""
        # Create a single XML file
        marc_file = tmp_path / "single.xml"
        marc_file.write_text('<?xml version="1.0"?><collection></collection>')

        loader = MarcLoader(str(marc_file))
        files = loader._get_marc_files()

        assert len(files) == 1
        assert files[0] == marc_file

    def test_get_marc_files_directory(self, tmp_path):
        """Test _get_marc_files with directory containing multiple XML files"""
        # Create multiple XML files
        (tmp_path / "file1.xml").write_text("<collection/>")
        (tmp_path / "file2.xml").write_text("<collection/>")
        (tmp_path / "file3.txt").write_text("not xml")  # Should be ignored

        loader = MarcLoader(str(tmp_path))
        files = loader._get_marc_files()

        assert len(files) == 2
        assert all(f.suffix == ".xml" for f in files)

    def test_get_marc_files_empty_directory(self, tmp_path):
        """Test _get_marc_files with empty directory"""
        loader = MarcLoader(str(tmp_path))
        files = loader._get_marc_files()

        assert files == []

    def test_get_marc_files_non_xml_extension(self, tmp_path):
        """Test _get_marc_files with non-XML extension"""
        # Create file with .marcxml extension
        marcxml_file = tmp_path / "records.marcxml"
        marcxml_file.write_text('<?xml version="1.0"?><collection/>')

        loader = MarcLoader(str(tmp_path))
        files = loader._get_marc_files()

        assert len(files) == 1
        assert files[0].suffix == ".marcxml"

    def test_extract_all_batches_xml_parse_error(self, tmp_path):
        """Test handling of XML parsing errors"""
        # Create invalid XML file
        bad_xml = tmp_path / "bad.xml"
        bad_xml.write_text("This is not valid XML <unclosed")

        loader = MarcLoader(str(bad_xml))
        batches = loader.extract_all_batches()

        # Should handle error and return empty
        assert batches == []

    def test_empty_xml_file(self, tmp_path):
        """Test handling of empty XML file"""
        empty_file = tmp_path / "empty.xml"
        empty_file.write_text('<?xml version="1.0"?><collection/>')

        loader = MarcLoader(str(empty_file))
        batches = loader.extract_all_batches()

        assert batches == []

    def test_xml_without_namespace(self, tmp_path):
        """Test handling XML without namespace"""
        xml_content = """<?xml version="1.0"?>
        <collection>
            <record>
                <controlfield tag="001">001</controlfield>
                <datafield tag="245" ind1="0" ind2="0">
                    <subfield code="a">Test Book</subfield>
                </datafield>
            </record>
        </collection>"""

        marc_file = tmp_path / "no_namespace.xml"
        marc_file.write_text(xml_content)

        loader = MarcLoader(str(marc_file))

        # Should handle records without namespace
        batches = loader.extract_all_batches()

        # Should get at least one batch with the record
        assert len(batches) == 1
        assert len(batches[0]) == 1
        assert batches[0][0].title == "Test Book"  # Minimal cleanup only


# =============================================================================
# BATCH PROCESSING TESTS
# =============================================================================


class TestMarcLoaderBatchProcessing:
    """Test batch processing functionality"""

    def test_extract_all_batches_creates_batches(self, tmp_path):
        """Test that records are properly batched"""
        # Create XML with multiple records
        xml_content = """<?xml version="1.0"?>
        <collection xmlns="http://www.loc.gov/MARC21/slim">
            <record><controlfield tag="001">001</controlfield></record>
            <record><controlfield tag="001">002</controlfield></record>
            <record><controlfield tag="001">003</controlfield></record>
            <record><controlfield tag="001">004</controlfield></record>
            <record><controlfield tag="001">005</controlfield></record>
        </collection>"""

        marc_file = tmp_path / "test.xml"
        marc_file.write_text(xml_content)

        # Create loader with batch size 2
        loader = MarcLoader(str(marc_file), batch_size=2)

        # Mock _extract_from_record to return simple publications
        def mock_extract(elem):
            control_field = elem.find(".//{http://www.loc.gov/MARC21/slim}controlfield[@tag='001']")
            if control_field is not None:
                return Publication(title=f"Book {control_field.text}", source_id=control_field.text)
            return None

        with patch.object(loader, "_extract_from_record", side_effect=mock_extract):
            batches = loader.extract_all_batches()

        # Should have 3 batches (2, 2, 1)
        assert len(batches) == 3
        assert len(batches[0]) == 2
        assert len(batches[1]) == 2
        assert len(batches[2]) == 1

    def test_batch_size_larger_than_records(self, tmp_path):
        """Test when batch size is larger than total records"""
        xml_content = """<?xml version="1.0"?>
        <collection xmlns="http://www.loc.gov/MARC21/slim">
            <record><controlfield tag="001">001</controlfield></record>
            <record><controlfield tag="001">002</controlfield></record>
        </collection>"""

        marc_file = tmp_path / "small.xml"
        marc_file.write_text(xml_content)

        loader = MarcLoader(str(marc_file), batch_size=100)

        with patch.object(loader, "_extract_from_record") as mock_extract:
            mock_extract.return_value = Publication(title="Test", source_id="001")
            batches = loader.extract_all_batches()

        # Should have single batch with all records
        assert len(batches) == 1
        assert len(batches[0]) == 2

    def test_element_clearing_during_parse(self, tmp_path):
        """Test that large files can be parsed efficiently in batches"""
        # Create large XML file
        xml_content = '<?xml version="1.0"?>\n<collection xmlns="http://www.loc.gov/MARC21/slim">\n'
        for i in range(100):
            xml_content += f"""<record>
                <controlfield tag="001">{i:05d}</controlfield>
                <datafield tag="245">
                    <subfield code="a">Book {i}</subfield>
                </datafield>
            </record>\n"""
        xml_content += "</collection>"

        marc_file = tmp_path / "large.xml"
        marc_file.write_text(xml_content)

        loader = MarcLoader(str(marc_file), batch_size=10)

        # Process the file - this tests that memory management works correctly
        # by successfully processing a large file in batches
        batches = loader.extract_all_batches()

        # Should have 10 batches of 10 records each
        assert len(batches) == 10
        for i, batch in enumerate(batches):
            assert len(batch) == 10
            # Verify first record in each batch
            assert batch[0].source_id == f"{i*10:05d}"
            assert batch[0].title == f"Book {i*10}"  # Minimal cleanup only


# =============================================================================
# STREAMING FUNCTIONALITY TESTS
# =============================================================================


class TestStreamingMarcLoader:
    """Test streaming functionality in MarcLoader"""

    @fixture
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

    @fixture
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
        assert batches[0][0].title == "Test title one"
        assert batches[0][1].title == "Test title two"
        assert batches[1][0].title == "Test title three"

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
                assert batch[0].title == "Test title one"
                assert batch[1].title == "Test title two"

            # Load and verify second pickle file
            with open(pickle_paths[1], "rb") as f:
                batch = pickle_load(f)
                assert len(batch) == 1
                assert batch[0].title == "Test title three"

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


# =============================================================================
# RECORD EXTRACTION TESTS
# =============================================================================


class TestMarcLoaderRecordExtraction:
    """Test _extract_from_record method edge cases"""

    def test_extract_from_record_minimal(self):
        """Test extracting from minimal MARC record"""
        loader = MarcLoader("dummy.xml")

        # Create minimal record with required title field
        record = fromstring(
            """
        <record xmlns="http://www.loc.gov/MARC21/slim">
            <controlfield tag="001">12345</controlfield>
            <datafield tag="245">
                <subfield code="a">Minimal Title</subfield>
            </datafield>
        </record>
        """
        )

        pub = loader._extract_from_record(record)

        assert pub is not None
        assert pub.source_id == "12345"
        assert pub.title == "Minimal Title"  # Minimal cleanup only

    def test_extract_from_record_with_exceptions(self):
        """Test extraction handles exceptions gracefully"""
        loader = MarcLoader("dummy.xml")

        # Create record that will cause issues
        record = fromstring("<record/>")  # Empty record

        # Test that exceptions in extraction return None
        pub = loader._extract_from_record(record)

        # Should return None on exception
        assert pub is None

    def test_extract_from_record_country_classification(self):
        """Test country classification extraction"""
        loader = MarcLoader("dummy.xml")

        # Create record with 008 field
        record = fromstring(
            """
        <record xmlns="http://www.loc.gov/MARC21/slim">
            <controlfield tag="001">12345</controlfield>
            <controlfield tag="008">210101s1950    xxu           000 0 eng d</controlfield>
            <datafield tag="245">
                <subfield code="a">Test Title</subfield>
            </datafield>
        </record>
        """
        )

        pub = loader._extract_from_record(record)

        assert pub is not None
        assert pub.country_code == "xxu"
        assert pub.country_classification == CountryClassification.US

    def test_extract_from_record_complete(self):
        """Test complete record extraction with all fields"""
        loader = MarcLoader("/dummy")

        record_xml = """<record xmlns="http://www.loc.gov/MARC21/slim">
            <controlfield tag="001">12345</controlfield>
            <controlfield tag="008">210101s1950    xxu           000 0 eng d</controlfield>
            <datafield tag="010">
                <subfield code="a">   55012345   </subfield>
            </datafield>
            <datafield tag="100">
                <subfield code="a">Smith, John, 1920-1990</subfield>
            </datafield>
            <datafield tag="245">
                <subfield code="a">Test Book</subfield>
                <subfield code="b">A Subtitle</subfield>
                <subfield code="c">by John Smith</subfield>
            </datafield>
            <datafield tag="250">
                <subfield code="a">2nd edition</subfield>
            </datafield>
            <datafield tag="264">
                <subfield code="a">New York</subfield>
                <subfield code="b">Test Publisher</subfield>
                <subfield code="c">1950</subfield>
            </datafield>
        </record>"""

        record = fromstring(record_xml)
        pub = loader._extract_from_record(record)

        assert pub is not None
        assert pub.source_id == "12345"
        assert pub.title == "Test Book A Subtitle"  # Minimal cleanup only
        assert pub.author == "by John Smith"  # Minimal cleanup only
        assert pub.main_author == "Smith, John"  # Minimal cleanup only
        assert pub.publisher == "Test Publisher"  # Minimal cleanup only
        assert pub.place == "New York"  # Minimal cleanup only
        assert pub.edition == "2nd edition"  # Edition kept as-is
        assert pub.lccn == "55012345"  # LCCN stripped
        assert pub.pub_date == "1950"
        assert pub.year == 1950

    def test_extract_from_record_title_with_parts(self):
        """Test title extraction with n and p subfields"""
        loader = MarcLoader("/dummy")

        record_xml = """<record>
            <datafield tag="245">
                <subfield code="a">Main Title</subfield>
                <subfield code="n">Part 1</subfield>
                <subfield code="p">The Beginning</subfield>
            </datafield>
        </record>"""

        record = fromstring(record_xml)
        pub = loader._extract_from_record(record)

        assert pub is not None
        assert pub.title == "Main Title Part 1 The Beginning"  # Minimal cleanup only

    def test_extract_from_record_no_title(self):
        """Test extraction when title is missing"""
        loader = MarcLoader("/dummy")

        record_xml = """<record>
            <controlfield tag="001">001</controlfield>
            <datafield tag="100">
                <subfield code="a">Author Name</subfield>
            </datafield>
        </record>"""

        record = fromstring(record_xml)
        pub = loader._extract_from_record(record)

        assert pub is None  # Should return None for missing title

    def test_extract_from_record_pub_date_from_008(self):
        """Test extracting publication date from 008 field"""
        loader = MarcLoader("/dummy")

        record_xml = """<record>
            <controlfield tag="008">210101s1955    xxu           000 0 eng d</controlfield>
            <datafield tag="245">
                <subfield code="a">Test Book</subfield>
            </datafield>
        </record>"""

        record = fromstring(record_xml)
        pub = loader._extract_from_record(record)

        assert pub is not None
        assert pub.pub_date == "1955"
        assert pub.year == 1955

    def test_extract_from_record_language_from_041(self):
        """Test extracting language from 041 field"""
        loader = MarcLoader("/dummy")

        record_xml = """<record>
            <datafield tag="041">
                <subfield code="a">fre</subfield>
            </datafield>
            <datafield tag="245">
                <subfield code="a">Test Book</subfield>
            </datafield>
        </record>"""

        record = fromstring(record_xml)
        pub = loader._extract_from_record(record)

        assert pub is not None
        assert pub.language_code == "fre"

    def test_extract_marc_field_with_namespace(self):
        """Test _extract_marc_field with namespaced XML"""
        loader = MarcLoader("/dummy")

        # Create record with namespace
        record_xml = """<record xmlns="http://www.loc.gov/MARC21/slim">
            <datafield tag="264">
                <subfield code="c">1950</subfield>
            </datafield>
        </record>"""

        record = fromstring(record_xml)
        ns = {"marc": "http://www.loc.gov/MARC21/slim"}

        field = loader._extract_marc_field(record, ns, ["264"], "c")

        assert field is not None
        assert field.text == "1950"

    def test_extract_marc_field_fallback_tags(self):
        """Test _extract_marc_field trying multiple tags"""
        loader = MarcLoader("/dummy")

        # Create record with only 260 field (fallback)
        record_xml = """<record xmlns="http://www.loc.gov/MARC21/slim">
            <datafield tag="260">
                <subfield code="b">Old Publisher Format</subfield>
            </datafield>
        </record>"""

        record = fromstring(record_xml)
        ns = {"marc": "http://www.loc.gov/MARC21/slim"}

        # Try 264 first, then 260
        field = loader._extract_marc_field(record, ns, ["264", "260"], "b")

        assert field is not None
        assert field.text == "Old Publisher Format"


# =============================================================================
# AUTHOR EXTRACTION TESTS (1xx fields)
# =============================================================================


class TestMarcAuthorExtraction:
    """Test extraction of 100, 110, 111 author fields"""

    def test_100_personal_name_extraction(self):
        """Test extraction of 100$a personal names"""
        extractor = MarcLoader("dummy_path")

        # Test basic personal name
        xml_string = """
        <record xmlns="http://www.loc.gov/MARC21/slim">
            <controlfield tag="001">test_id</controlfield>
            <controlfield tag="008">850101s1985    nyu           000 0 eng d</controlfield>
            <datafield tag="100" ind1="1" ind2=" ">
                <subfield code="a">Smith, John,</subfield>
                <subfield code="d">1945-</subfield>
            </datafield>
            <datafield tag="245" ind1="1" ind2="0">
                <subfield code="a">Test book</subfield>
                <subfield code="c">by John Smith.</subfield>
            </datafield>
        </record>
        """

        record = fromstring(xml_string)
        pub = extractor._extract_from_record(record)

        assert pub is not None
        assert pub.original_author == "by John Smith."
        assert pub.original_main_author == "Smith, John,"  # Date cleaned

    def test_100_with_full_dates(self):
        """Test cleaning dates from 100$a field"""
        extractor = MarcLoader("dummy_path")

        xml_string = """
        <record xmlns="http://www.loc.gov/MARC21/slim">
            <controlfield tag="001">test_id</controlfield>
            <controlfield tag="008">850101s1985    nyu           000 0 eng d</controlfield>
            <datafield tag="100" ind1="1" ind2=" ">
                <subfield code="a">Doe, Jane, 1920-1995</subfield>
            </datafield>
            <datafield tag="245" ind1="1" ind2="0">
                <subfield code="a">Another book</subfield>
            </datafield>
        </record>
        """

        record = fromstring(xml_string)
        pub = extractor._extract_from_record(record)

        assert pub is not None
        assert pub.original_main_author == "Doe, Jane"  # Dates cleaned

    def test_110_corporate_name_extraction(self):
        """Test extraction of 110$a corporate names"""
        extractor = MarcLoader("dummy_path")

        xml_string = """
        <record xmlns="http://www.loc.gov/MARC21/slim">
            <controlfield tag="001">test_id</controlfield>
            <controlfield tag="008">850101s1985    nyu           000 0 eng d</controlfield>
            <datafield tag="110" ind1="2" ind2=" ">
                <subfield code="a">Acme Corporation</subfield>
            </datafield>
            <datafield tag="245" ind1="1" ind2="0">
                <subfield code="a">Corporate publication</subfield>
            </datafield>
        </record>
        """

        record = fromstring(xml_string)
        pub = extractor._extract_from_record(record)

        assert pub is not None
        assert pub.original_main_author == "Acme Corporation"

    def test_111_meeting_name_extraction(self):
        """Test extraction of 111$a meeting names"""
        extractor = MarcLoader("dummy_path")

        xml_string = """
        <record xmlns="http://www.loc.gov/MARC21/slim">
            <controlfield tag="001">test_id</controlfield>
            <controlfield tag="008">850101s1985    nyu           000 0 eng d</controlfield>
            <datafield tag="111" ind1="2" ind2=" ">
                <subfield code="a">International Conference on Testing</subfield>
            </datafield>
            <datafield tag="245" ind1="1" ind2="0">
                <subfield code="a">Conference proceedings</subfield>
            </datafield>
        </record>
        """

        record = fromstring(xml_string)
        pub = extractor._extract_from_record(record)

        assert pub is not None
        assert pub.original_main_author == "International Conference on Testing"

    def test_priority_order_100_over_110(self):
        """Test that 100 takes priority over 110"""
        extractor = MarcLoader("dummy_path")

        xml_string = """
        <record xmlns="http://www.loc.gov/MARC21/slim">
            <controlfield tag="001">test_id</controlfield>
            <controlfield tag="008">850101s1985    nyu           000 0 eng d</controlfield>
            <datafield tag="100" ind1="1" ind2=" ">
                <subfield code="a">Smith, John</subfield>
            </datafield>
            <datafield tag="110" ind1="2" ind2=" ">
                <subfield code="a">Acme Corporation</subfield>
            </datafield>
            <datafield tag="245" ind1="1" ind2="0">
                <subfield code="a">Test book</subfield>
            </datafield>
        </record>
        """

        record = fromstring(xml_string)
        pub = extractor._extract_from_record(record)

        assert pub is not None
        assert pub.original_main_author == "Smith, John"  # 100 wins over 110

    def test_no_1xx_fields(self):
        """Test handling when no 1xx fields are present"""
        extractor = MarcLoader("dummy_path")

        xml_string = """
        <record xmlns="http://www.loc.gov/MARC21/slim">
            <controlfield tag="001">test_id</controlfield>
            <controlfield tag="008">850101s1985    nyu           000 0 eng d</controlfield>
            <datafield tag="245" ind1="1" ind2="0">
                <subfield code="a">Anonymous work</subfield>
                <subfield code="c">by unknown author.</subfield>
            </datafield>
        </record>
        """

        record = fromstring(xml_string)
        pub = extractor._extract_from_record(record)

        assert pub is not None
        assert pub.original_author == "by unknown author."
        assert pub.original_main_author is None  # No 1xx field

    def test_both_245c_and_1xx_present(self):
        """Test that both author fields are extracted when present"""
        extractor = MarcLoader("dummy_path")

        xml_string = """
        <record xmlns="http://www.loc.gov/MARC21/slim">
            <controlfield tag="001">test_id</controlfield>
            <controlfield tag="008">850101s1985    nyu           000 0 eng d</controlfield>
            <datafield tag="100" ind1="1" ind2=" ">
                <subfield code="a">Johnson, Mary, 1960-</subfield>
            </datafield>
            <datafield tag="245" ind1="1" ind2="0">
                <subfield code="a">Research methods</subfield>
                <subfield code="c">by Dr. Mary Johnson.</subfield>
            </datafield>
        </record>
        """

        record = fromstring(xml_string)
        pub = extractor._extract_from_record(record)

        assert pub is not None
        assert pub.original_author == "by Dr. Mary Johnson."
        assert pub.original_main_author == "Johnson, Mary"  # Date cleaned

    def test_extract_from_record_corporate_author(self):
        """Test extraction of corporate author (110 field)"""
        loader = MarcLoader("/dummy")

        record_xml = """<record>
            <datafield tag="110">
                <subfield code="a">United Nations</subfield>
            </datafield>
            <datafield tag="245">
                <subfield code="a">Annual Report</subfield>
            </datafield>
        </record>"""

        record = fromstring(record_xml)
        pub = loader._extract_from_record(record)

        assert pub is not None
        assert pub.main_author == "United Nations"  # Minimal cleanup only

    def test_extract_from_record_meeting_author(self):
        """Test extraction of meeting author (111 field)"""
        loader = MarcLoader("/dummy")

        record_xml = """<record>
            <datafield tag="111">
                <subfield code="a">International Conference on Computing</subfield>
            </datafield>
            <datafield tag="245">
                <subfield code="a">Conference Proceedings</subfield>
            </datafield>
        </record>"""

        record = fromstring(record_xml)
        pub = loader._extract_from_record(record)

        assert pub is not None
        assert pub.main_author == "International Conference on Computing"  # Minimal cleanup only


# =============================================================================
# BRACKETED CONTENT REMOVAL TESTS
# =============================================================================


class TestBracketedContentInMarcTitles:
    """Test that bracketed content is removed from MARC titles during extraction"""

    @fixture
    def marc_with_brackets(self):
        """Create MARC XML with titles containing bracketed content"""
        return """<?xml version="1.0" encoding="UTF-8"?>
<collection xmlns="http://www.loc.gov/MARC21/slim">
  <record>
    <controlfield tag="001">test001</controlfield>
    <controlfield tag="008">230101s2023    nyu           000 0 eng d</controlfield>
    <datafield tag="245" ind1="1" ind2="0">
      <subfield code="a">The Great Adventure</subfield>
      <subfield code="b">[microform] :</subfield>
      <subfield code="c">by John Smith.</subfield>
    </datafield>
    <datafield tag="264" ind1=" " ind2="1">
      <subfield code="a">New York :</subfield>
      <subfield code="b">Test Publisher,</subfield>
      <subfield code="c">2023.</subfield>
    </datafield>
  </record>
  <record>
    <controlfield tag="001">test002</controlfield>
    <controlfield tag="008">230101s2023    nyu           000 0 eng d</controlfield>
    <datafield tag="245" ind1="1" ind2="0">
      <subfield code="a">Complete Works [electronic resource]</subfield>
      <subfield code="n">Volume 1</subfield>
      <subfield code="p">Early Writings</subfield>
    </datafield>
    <datafield tag="264" ind1=" " ind2="1">
      <subfield code="a">New York :</subfield>
      <subfield code="b">Digital Press,</subfield>
      <subfield code="c">2023.</subfield>
    </datafield>
  </record>
  <record>
    <controlfield tag="001">test003</controlfield>
    <controlfield tag="008">230101s2023    nyu           000 0 eng d</controlfield>
    <datafield tag="245" ind1="1" ind2="0">
      <subfield code="a">Poetry Collection</subfield>
      <subfield code="b">[sound recording] [1st ed.]</subfield>
    </datafield>
    <datafield tag="264" ind1=" " ind2="1">
      <subfield code="a">New York :</subfield>
      <subfield code="b">Audio Books,</subfield>
      <subfield code="c">2023.</subfield>
    </datafield>
  </record>
</collection>"""

    def test_brackets_removed_from_title_extraction(self, marc_with_brackets):
        """Test that bracketed content is removed during MARC extraction"""
        with NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as f:
            f.write(marc_with_brackets)
            f.flush()

            try:
                loader = MarcLoader(f.name)
                batches = loader.extract_all_batches()
                assert len(batches) == 1
                pubs = batches[0]
                assert len(pubs) == 3

                # First record: brackets in subfield b
                pub1 = pubs[0]
                assert pub1.original_title == "The Great Adventure :"
                assert "[microform]" not in pub1.original_title

                # Second record: brackets in subfield a
                pub2 = pubs[1]
                assert pub2.original_title == "Complete Works Volume 1 Early Writings"
                assert "[electronic resource]" not in pub2.original_title

                # Third record: multiple brackets in subfield b
                pub3 = pubs[2]
                assert pub3.original_title == "Poetry Collection"
                assert "[sound recording]" not in pub3.original_title
                assert "[1st ed.]" not in pub3.original_title

            finally:
                Path(f.name).unlink()

    def test_extract_from_record_bracketed_content_removal(self):
        """Test removal of bracketed content from title"""
        loader = MarcLoader("/dummy")

        record_xml = """<record>
            <datafield tag="245">
                <subfield code="a">Test Book [microform]</subfield>
            </datafield>
        </record>"""

        record = fromstring(record_xml)
        pub = loader._extract_from_record(record)

        assert pub is not None
        assert pub.title == "Test Book"  # Minimal cleanup only

    def test_empty_title_after_bracket_removal(self):
        """Test handling when title becomes empty after bracket removal"""
        marc_xml = """<?xml version="1.0" encoding="UTF-8"?>
<collection xmlns="http://www.loc.gov/MARC21/slim">
  <record>
    <controlfield tag="001">test001</controlfield>
    <controlfield tag="008">230101s2023    nyu           000 0 eng d</controlfield>
    <datafield tag="245" ind1="1" ind2="0">
      <subfield code="a">[microform]</subfield>
    </datafield>
    <datafield tag="264" ind1=" " ind2="1">
      <subfield code="a">New York :</subfield>
      <subfield code="b">Test Publisher,</subfield>
      <subfield code="c">2023.</subfield>
    </datafield>
  </record>
</collection>"""

        with NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as f:
            f.write(marc_xml)
            f.flush()

            try:
                loader = MarcLoader(f.name)
                batches = loader.extract_all_batches()
                # Record should be skipped because title becomes empty
                assert len(batches) == 0
            finally:
                Path(f.name).unlink()

    def test_brackets_in_multiple_subfields(self):
        """Test brackets spread across multiple subfields"""
        marc_xml = """<?xml version="1.0" encoding="UTF-8"?>
<collection xmlns="http://www.loc.gov/MARC21/slim">
  <record>
    <controlfield tag="001">test001</controlfield>
    <controlfield tag="008">230101s2023    nyu           000 0 eng d</controlfield>
    <datafield tag="245" ind1="1" ind2="0">
      <subfield code="a">Main Title [draft]</subfield>
      <subfield code="b">: subtitle [microform]</subfield>
      <subfield code="n">[Part 1]</subfield>
      <subfield code="p">Introduction [revised]</subfield>
    </datafield>
    <datafield tag="264" ind1=" " ind2="1">
      <subfield code="a">New York :</subfield>
      <subfield code="b">Test Publisher,</subfield>
      <subfield code="c">2023.</subfield>
    </datafield>
  </record>
</collection>"""

        with NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as f:
            f.write(marc_xml)
            f.flush()

            try:
                loader = MarcLoader(f.name)
                batches = loader.extract_all_batches()
                assert len(batches) == 1
                pub = batches[0][0]

                # All bracketed content should be removed
                assert pub.original_title == "Main Title : subtitle Introduction"
                assert "[draft]" not in pub.original_title
                assert "[microform]" not in pub.original_title
                assert "[Part 1]" not in pub.original_title
                assert "[revised]" not in pub.original_title

            finally:
                Path(f.name).unlink()

    def test_preserves_non_bracketed_content(self):
        """Test that parentheses and other brackets are preserved"""
        marc_xml = """<?xml version="1.0" encoding="UTF-8"?>
<collection xmlns="http://www.loc.gov/MARC21/slim">
  <record>
    <controlfield tag="001">test001</controlfield>
    <controlfield tag="008">230101s2023    nyu           000 0 eng d</controlfield>
    <datafield tag="245" ind1="1" ind2="0">
      <subfield code="a">Title (with parentheses) [microform]</subfield>
      <subfield code="b">: {with braces}</subfield>
    </datafield>
    <datafield tag="264" ind1=" " ind2="1">
      <subfield code="a">New York :</subfield>
      <subfield code="b">Test Publisher,</subfield>
      <subfield code="c">2023.</subfield>
    </datafield>
  </record>
</collection>"""

        with NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as f:
            f.write(marc_xml)
            f.flush()

            try:
                loader = MarcLoader(f.name)
                batches = loader.extract_all_batches()
                assert len(batches) == 1
                pub = batches[0][0]

                # Only square brackets should be removed
                assert pub.original_title == "Title (with parentheses) : {with braces}"
                assert "(with parentheses)" in pub.original_title
                assert "{with braces}" in pub.original_title
                assert "[microform]" not in pub.original_title

            finally:
                Path(f.name).unlink()


# =============================================================================
# FILTERING TESTS
# =============================================================================


class TestMarcLoaderFiltering:
    """Test filtering logic in MarcLoader"""

    def test_should_include_record_with_reason_no_year(self):
        """Test filtering when publication has no year"""
        loader = MarcLoader("dummy.xml", min_year=1950, max_year=1960)

        pub = Publication(title="No Year Book", source_id="001")
        # No pub_date set

        include, reason = loader._should_include_record_with_reason(pub)

        assert include is False
        assert reason == "no_year"

    def test_should_include_record_with_reason_year_out_of_range(self):
        """Test filtering when year is out of range"""
        loader = MarcLoader("dummy.xml", min_year=1950, max_year=1960)

        # Before range
        pub1 = Publication(title="Old Book", pub_date="1940", source_id="001")
        include1, reason1 = loader._should_include_record_with_reason(pub1)
        assert include1 is False
        assert reason1 == "year_out_of_range"

        # After range
        pub2 = Publication(title="New Book", pub_date="1970", source_id="002")
        include2, reason2 = loader._should_include_record_with_reason(pub2)
        assert include2 is False
        assert reason2 == "year_out_of_range"

        # In range
        pub3 = Publication(title="Good Book", pub_date="1955", source_id="003")
        include3, reason3 = loader._should_include_record_with_reason(pub3)
        assert include3 is True
        assert reason3 is None

    def test_should_include_record_with_reason_non_us(self):
        """Test filtering for US-only mode"""
        loader = MarcLoader("dummy.xml", us_only=True)

        # Non-US publication
        pub1 = Publication(
            title="British Book",
            pub_date="1950",
            source_id="001",
            country_code="enk",
            country_classification=CountryClassification.NON_US,
        )
        include1, reason1 = loader._should_include_record_with_reason(pub1)
        assert include1 is False
        assert reason1 == "non_us"

        # US publication
        pub2 = Publication(
            title="American Book",
            pub_date="1950",
            source_id="002",
            country_code="xxu",
            country_classification=CountryClassification.US,
        )
        include2, reason2 = loader._should_include_record_with_reason(pub2)
        assert include2 is True
        assert reason2 is None

    def test_should_include_record_all_filters(self):
        """Test combination of all filters"""
        loader = MarcLoader("dummy.xml", min_year=1950, max_year=1960, us_only=True)

        # Good record - passes all filters
        pub = Publication(
            title="US Book 1955",
            pub_date="1955",
            source_id="001",
            country_code="xxu",
            country_classification=CountryClassification.US,
        )

        include, reason = loader._should_include_record_with_reason(pub)
        assert include is True
        assert reason is None

    def test_extract_all_batches_filtering_stats(self, tmp_path):
        """Test that filtering statistics are tracked correctly"""
        # Create XML with records that will be filtered
        xml_content = """<?xml version="1.0"?>
        <collection xmlns="http://www.loc.gov/MARC21/slim">
            <record><controlfield tag="001">001</controlfield></record>
            <record><controlfield tag="001">002</controlfield></record>
            <record><controlfield tag="001">003</controlfield></record>
        </collection>"""

        marc_file = tmp_path / "test.xml"
        marc_file.write_text(xml_content)

        # Create loader with filters
        loader = MarcLoader(str(marc_file), min_year=1950, max_year=1960, us_only=True)

        # Mock different filtering scenarios
        pubs = [
            Publication(title="No Year", source_id="001"),  # No year
            Publication(
                title="Non-US",
                pub_date="1955",
                source_id="002",
                country_classification=CountryClassification.NON_US,
            ),  # Non-US
            Publication(
                title="Good",
                pub_date="1955",
                source_id="003",
                country_classification=CountryClassification.US,
            ),  # Should pass
        ]

        extract_calls = 0

        def mock_extract(elem):
            nonlocal extract_calls
            result = pubs[extract_calls] if extract_calls < len(pubs) else None
            extract_calls += 1
            return result

        with patch.object(loader, "_extract_from_record", side_effect=mock_extract):
            batches = loader.extract_all_batches()

        # Should have 1 batch with 1 record
        assert len(batches) == 1
        assert len(batches[0]) == 1
        assert batches[0][0].title == "Good"  # Minimal cleanup only


# =============================================================================
# YEAR FILTERING TESTS
# =============================================================================


class TestYearFiltering:
    """Test year filtering functionality"""

    def test_should_include_record_no_filters(self):
        """Test that all records are included when no year filters are set"""
        extractor = MarcLoader("dummy_path")

        # Create test publications with different years
        pub_1940 = Publication(
            "Test 1940", pub_date="1940", country_classification=CountryClassification.US
        )
        pub_1955 = Publication(
            "Test 1955", pub_date="1955", country_classification=CountryClassification.US
        )
        pub_2020 = Publication(
            "Test 2020", pub_date="2020", country_classification=CountryClassification.US
        )
        pub_no_year = Publication("Test No Year", country_classification=CountryClassification.US)

        # All should be included when no filters are set
        assert extractor._should_include_record(pub_1940) is True
        assert extractor._should_include_record(pub_1955) is True
        assert extractor._should_include_record(pub_2020) is True
        assert extractor._should_include_record(pub_no_year) is True

    def test_should_include_record_min_year_only(self):
        """Test filtering with only minimum year set"""
        extractor = MarcLoader("dummy_path", min_year=1950)

        pub_1940 = Publication(
            "Test 1940", pub_date="1940", country_classification=CountryClassification.US
        )
        pub_1950 = Publication(
            "Test 1950", pub_date="1950", country_classification=CountryClassification.US
        )
        pub_1960 = Publication(
            "Test 1960", pub_date="1960", country_classification=CountryClassification.US
        )

        assert extractor._should_include_record(pub_1940) is False  # Too old
        assert extractor._should_include_record(pub_1950) is True  # Exactly min year
        assert extractor._should_include_record(pub_1960) is True  # After min year

    def test_should_include_record_max_year_only(self):
        """Test filtering with only maximum year set"""
        extractor = MarcLoader("dummy_path", max_year=1960)

        pub_1940 = Publication(
            "Test 1940", pub_date="1940", country_classification=CountryClassification.US
        )
        pub_1960 = Publication(
            "Test 1960", pub_date="1960", country_classification=CountryClassification.US
        )
        pub_1970 = Publication(
            "Test 1970", pub_date="1970", country_classification=CountryClassification.US
        )

        assert extractor._should_include_record(pub_1940) is True  # Before max year
        assert extractor._should_include_record(pub_1960) is True  # Exactly max year
        assert extractor._should_include_record(pub_1970) is False  # Too new

    def test_should_include_record_year_range(self):
        """Test filtering with both min and max year set (year range)"""
        extractor = MarcLoader("dummy_path", min_year=1950, max_year=1960)

        pub_1940 = Publication(
            "Test 1940", pub_date="1940", country_classification=CountryClassification.US
        )
        pub_1950 = Publication(
            "Test 1950", pub_date="1950", country_classification=CountryClassification.US
        )
        pub_1955 = Publication(
            "Test 1955", pub_date="1955", country_classification=CountryClassification.US
        )
        pub_1960 = Publication(
            "Test 1960", pub_date="1960", country_classification=CountryClassification.US
        )
        pub_1970 = Publication(
            "Test 1970", pub_date="1970", country_classification=CountryClassification.US
        )

        assert extractor._should_include_record(pub_1940) is False  # Too old
        assert extractor._should_include_record(pub_1950) is True  # Exactly min year
        assert extractor._should_include_record(pub_1955) is True  # In range
        assert extractor._should_include_record(pub_1960) is True  # Exactly max year
        assert extractor._should_include_record(pub_1970) is False  # Too new

    def test_should_include_record_single_year(self):
        """Test filtering to a single year (min_year == max_year)"""
        extractor = MarcLoader("dummy_path", min_year=1955, max_year=1955)

        pub_1954 = Publication(
            "Test 1954", pub_date="1954", country_classification=CountryClassification.US
        )
        pub_1955 = Publication(
            "Test 1955", pub_date="1955", country_classification=CountryClassification.US
        )
        pub_1956 = Publication(
            "Test 1956", pub_date="1956", country_classification=CountryClassification.US
        )

        assert extractor._should_include_record(pub_1954) is False  # Before target year
        assert extractor._should_include_record(pub_1955) is True  # Exactly target year
        assert extractor._should_include_record(pub_1956) is False  # After target year

    def test_should_include_record_no_year_always_included(self):
        """Test that records without publication years are excluded when year filtering is active"""
        extractor_min = MarcLoader("dummy_path", min_year=1950)
        extractor_max = MarcLoader("dummy_path", max_year=1960)
        extractor_range = MarcLoader("dummy_path", min_year=1950, max_year=1960)
        extractor_no_filter = MarcLoader("dummy_path")

        pub_no_year = Publication("Test No Year", country_classification=CountryClassification.US)

        # Records without years should be excluded when year filtering is active
        assert extractor_min._should_include_record(pub_no_year) is False
        assert extractor_max._should_include_record(pub_no_year) is False
        assert extractor_range._should_include_record(pub_no_year) is False

        # But included when no year filtering
        assert extractor_no_filter._should_include_record(pub_no_year) is True

    def test_extractor_constructor_accepts_max_year(self):
        """Test that MarcLoader constructor accepts max_year parameter"""
        # Test with min_year only
        extractor1 = MarcLoader("dummy_path", min_year=1950)
        assert extractor1.min_year == 1950
        assert extractor1.max_year is None

        # Test with max_year only
        extractor2 = MarcLoader("dummy_path", max_year=1960)
        assert extractor2.min_year is None
        assert extractor2.max_year == 1960

        # Test with both min_year and max_year
        extractor3 = MarcLoader("dummy_path", min_year=1950, max_year=1960)
        assert extractor3.min_year == 1950
        assert extractor3.max_year == 1960

        # Test with neither
        extractor4 = MarcLoader("dummy_path")
        assert extractor4.min_year is None
        assert extractor4.max_year is None

    def test_year_boundary_conditions(self):
        """Test boundary conditions for year filtering"""
        extractor = MarcLoader("dummy_path", min_year=1950, max_year=1960)

        # Test exact boundaries
        pub_min_boundary = Publication(
            "Test Min Boundary", pub_date="1950", country_classification=CountryClassification.US
        )
        pub_max_boundary = Publication(
            "Test Max Boundary", pub_date="1960", country_classification=CountryClassification.US
        )

        # Boundary values should be included (inclusive range)
        assert extractor._should_include_record(pub_min_boundary) is True
        assert extractor._should_include_record(pub_max_boundary) is True

        # Just outside boundaries should be excluded
        pub_below_min = Publication(
            "Test Below Min", pub_date="1949", country_classification=CountryClassification.US
        )
        pub_above_max = Publication(
            "Test Above Max", pub_date="1961", country_classification=CountryClassification.US
        )

        assert extractor._should_include_record(pub_below_min) is False
        assert extractor._should_include_record(pub_above_max) is False

    def test_year_filtering_with_various_date_formats(self):
        """Test year filtering works with different publication date formats"""
        extractor = MarcLoader("dummy_path", min_year=1950, max_year=1960)

        # Test different date formats that should all extract to year 1955
        pub_year_only = Publication(
            "Test Year Only", pub_date="1955", country_classification=CountryClassification.US
        )
        pub_full_date = Publication(
            "Test Full Date", pub_date="1955-06-15", country_classification=CountryClassification.US
        )
        pub_complex_date = Publication(
            "Test Complex Date", pub_date="c1955", country_classification=CountryClassification.US
        )

        # All should be included as they're in the 1950-1960 range
        assert extractor._should_include_record(pub_year_only) is True
        assert extractor._should_include_record(pub_full_date) is True
        assert extractor._should_include_record(pub_complex_date) is True


# =============================================================================
# US-ONLY FILTERING TESTS
# =============================================================================


class TestUSOnlyFiltering:
    """Test US-only filtering functionality"""

    @fixture
    def us_publication(self):
        """Create a US publication for testing"""
        return Publication(
            title="Test US Book",
            author="US Author",
            pub_date="1950",
            source_id="us_001",
            country_classification=CountryClassification.US,
        )

    @fixture
    def non_us_publication(self):
        """Create a non-US publication for testing"""
        return Publication(
            title="Test Foreign Book",
            author="Foreign Author",
            pub_date="1950",
            source_id="non_us_001",
            country_classification=CountryClassification.NON_US,
        )

    @fixture
    def unknown_country_publication(self):
        """Create a publication with unknown country for testing"""
        return Publication(
            title="Test Unknown Book",
            author="Unknown Author",
            pub_date="1950",
            source_id="unknown_001",
            country_classification=CountryClassification.UNKNOWN,
        )

    def test_us_only_filter_includes_us_records(self, us_publication):
        """Test that US-only filter includes US records"""
        extractor = MarcLoader("dummy.xml", us_only=True)
        assert extractor._should_include_record(us_publication) is True

    def test_us_only_filter_excludes_non_us_records(self, non_us_publication):
        """Test that US-only filter excludes non-US records"""
        extractor = MarcLoader("dummy.xml", us_only=True)
        assert extractor._should_include_record(non_us_publication) is False

    def test_us_only_filter_excludes_unknown_country_records(self, unknown_country_publication):
        """Test that US-only filter excludes unknown country records"""
        extractor = MarcLoader("dummy.xml", us_only=True)
        assert extractor._should_include_record(unknown_country_publication) is False

    def test_us_only_false_includes_all_countries(
        self, us_publication, non_us_publication, unknown_country_publication
    ):
        """Test that us_only=False includes all country classifications"""
        extractor = MarcLoader("dummy.xml", us_only=False)
        assert extractor._should_include_record(us_publication) is True
        assert extractor._should_include_record(non_us_publication) is True
        assert extractor._should_include_record(unknown_country_publication) is True

    def test_us_only_with_year_filtering(self):
        """Test that US-only filter works with year filtering"""
        # Create US publication that should be filtered by year
        old_us_pub = Publication(
            title="Old US Book",
            author="US Author",
            pub_date="1920",
            source_id="old_us_001",
            country_classification=CountryClassification.US,
        )
        old_us_pub.year = 1920

        # Create non-US publication that should be filtered by country
        new_non_us_pub = Publication(
            title="New Foreign Book",
            author="Foreign Author",
            pub_date="1950",
            source_id="new_non_us_001",
            country_classification=CountryClassification.NON_US,
        )
        new_non_us_pub.year = 1950

        # Create US publication that should pass both filters
        new_us_pub = Publication(
            title="New US Book",
            author="US Author",
            pub_date="1950",
            source_id="new_us_001",
            country_classification=CountryClassification.US,
        )
        new_us_pub.year = 1950

        extractor = MarcLoader("dummy.xml", min_year=1930, us_only=True)

        # Old US publication filtered by year
        assert extractor._should_include_record(old_us_pub) is False
        # Non-US publication filtered by country
        assert extractor._should_include_record(new_non_us_pub) is False
        # US publication passes both filters
        assert extractor._should_include_record(new_us_pub) is True

    def test_us_only_with_no_year(self):
        """Test that US-only filter handles publications with no year"""
        us_pub_no_year = Publication(
            title="US Book No Year",
            author="US Author",
            pub_date="",
            source_id="us_no_year_001",
            country_classification=CountryClassification.US,
        )
        us_pub_no_year.year = None

        non_us_pub_no_year = Publication(
            title="Foreign Book No Year",
            author="Foreign Author",
            pub_date="",
            source_id="non_us_no_year_001",
            country_classification=CountryClassification.NON_US,
        )
        non_us_pub_no_year.year = None

        extractor = MarcLoader("dummy.xml", us_only=True)

        # US publication with no year should be included
        assert extractor._should_include_record(us_pub_no_year) is True
        # Non-US publication with no year should be excluded
        assert extractor._should_include_record(non_us_pub_no_year) is False

    def test_command_line_argument_parsing(self):
        """Test that --us-only command line argument is parsed correctly"""
        # Test without --us-only flag
        parser = ArgumentParser()
        parser.add_argument("--us-only", action="store_true", help="Test flag")

        args_no_flag = parser.parse_args([])
        assert args_no_flag.us_only is False

        # Test with --us-only flag
        args_with_flag = parser.parse_args(["--us-only"])
        assert args_with_flag.us_only is True

    def test_extractor_constructor_accepts_us_only_parameter(self):
        """Test that MarcLoader accepts us_only parameter"""
        # Test default value
        extractor_default = MarcLoader("dummy.xml")
        assert extractor_default.us_only is False

        # Test explicit False
        extractor_false = MarcLoader("dummy.xml", us_only=False)
        assert extractor_false.us_only is False

        # Test explicit True
        extractor_true = MarcLoader("dummy.xml", us_only=True)
        assert extractor_true.us_only is True

    def test_us_only_filter_edge_cases(self):
        """Test edge cases for US-only filtering"""
        extractor = MarcLoader("dummy.xml", us_only=True)

        # Test with publication that has all the other attributes but wrong country
        edge_case_pub = Publication(
            title="Edge Case Book",
            author="Edge Author",
            pub_date="1950",
            source_id="edge_001",
            country_classification=CountryClassification.NON_US,
        )
        edge_case_pub.year = 1950

        assert extractor._should_include_record(edge_case_pub) is False


# =============================================================================
# BEYOND DATA YEAR FILTERING TESTS
# =============================================================================


class TestMarcBeyondDataFiltering:
    """Test filtering of MARC records beyond available data"""

    def create_marc_xml(self, years: list[str]) -> str:
        """Create a temporary MARC XML file with records for specified years"""
        collection = Element("collection")

        for i, year in enumerate(years):
            record = SubElement(collection, "record")

            # Add control field 001 (record ID)
            control_001 = SubElement(record, "controlfield", tag="001")
            control_001.text = f"test_{i:03d}"

            # Add field 245 (title)
            field_245 = SubElement(record, "datafield", tag="245")
            subfield_a = SubElement(field_245, "subfield", code="a")
            subfield_a.text = f"Test Book {year}"

            # Add field 264 (publication info) with year
            field_264 = SubElement(record, "datafield", tag="264")
            subfield_c = SubElement(field_264, "subfield", code="c")
            subfield_c.text = year

            # Add field 008 (control info) with country code
            control_008 = SubElement(record, "controlfield", tag="008")
            control_008.text = "      s        xxu                 eng d"

        # Create temporary file and write XML
        with NamedTemporaryFile(mode="wb", suffix=".xml", delete=False) as f:
            f.write(tostring(collection, encoding="utf-8"))
            return f.name

    def test_filter_beyond_max_data_year(self):
        """Test that records beyond max_data_year are filtered out"""
        # Create MARC file with records from various years
        years = ["1975", "1990", "2000", "2005", "2010", "2020"]
        marc_file = self.create_marc_xml(years)

        try:
            # Create loader with max_data_year=2001 (typical renewal data limit)
            loader = MarcLoader(marc_path=marc_file, batch_size=10, max_data_year=2001)

            # Extract all batches
            batches = loader.extract_all_batches()

            # Flatten to get all publications
            all_pubs = [pub for batch in batches for pub in batch]

            # Should have only records from 1975, 1990, 2000 (not 2005, 2010, 2020)
            assert len(all_pubs) == 3

            # Check years of included records
            years_included = [pub.year for pub in all_pubs]
            assert sorted(years_included) == [1975, 1990, 2000]

        finally:
            # Clean up temp file
            Path(marc_file).unlink(missing_ok=True)

    def test_no_filtering_without_max_data_year(self):
        """Test that all records are included when max_data_year is not set"""
        # Create MARC file with records from various years
        years = ["1975", "1990", "2000", "2005", "2010", "2020"]
        marc_file = self.create_marc_xml(years)

        try:
            # Create loader WITHOUT max_data_year
            loader = MarcLoader(marc_path=marc_file, batch_size=10)

            # Extract all batches
            batches = loader.extract_all_batches()

            # Flatten to get all publications
            all_pubs = [pub for batch in batches for pub in batch]

            # Should have all 6 records
            assert len(all_pubs) == 6

        finally:
            # Clean up temp file
            Path(marc_file).unlink(missing_ok=True)

    def test_max_year_vs_max_data_year_interaction(self):
        """Test interaction between max_year and max_data_year parameters"""
        # Create MARC file with records from various years
        years = ["1975", "1990", "1995", "2000", "2005", "2010"]
        marc_file = self.create_marc_xml(years)

        try:
            # Create loader with both max_year=1998 and max_data_year=2001
            # max_year should take precedence for earlier cutoff
            loader = MarcLoader(
                marc_path=marc_file, batch_size=10, max_year=1998, max_data_year=2001
            )

            # Extract all batches
            batches = loader.extract_all_batches()

            # Flatten to get all publications
            all_pubs = [pub for batch in batches for pub in batch]

            # Should have only records up to 1998 (1975, 1990, 1995)
            assert len(all_pubs) == 3
            years_included = [pub.year for pub in all_pubs]
            assert sorted(years_included) == [1975, 1990, 1995]

        finally:
            # Clean up temp file
            Path(marc_file).unlink(missing_ok=True)

    def test_filter_reason_tracking(self):
        """Test that filter reasons are correctly tracked"""
        # Create MARC file with records from various years
        years = ["1920", "1975", "2000", "2010", "2020"]
        marc_file = self.create_marc_xml(years)

        try:
            # Create loader with min_year=1930 and max_data_year=2001
            loader = MarcLoader(
                marc_path=marc_file, batch_size=10, min_year=1930, max_data_year=2001
            )

            # Count filtered records by reason
            included_count = 0

            for batch in loader.iter_batches():
                included_count += len(batch)

            # From the years provided:
            # - 1920: filtered by min_year (year_out_of_range)
            # - 1975, 2000: included
            # - 2010, 2020: filtered by max_data_year (beyond_available_data)
            assert included_count == 2  # 1975 and 2000

        finally:
            # Clean up temp file
            Path(marc_file).unlink(missing_ok=True)


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestStreamingIntegration:
    """Integration tests for streaming with other components"""

    @fixture
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
        assert pub1.title == "Test title one"
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


# =============================================================================
# ERROR HANDLING TESTS
# =============================================================================


class TestStreamingErrorHandling:
    """Test error handling in streaming functionality"""

    @fixture
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
