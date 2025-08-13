# tests/test_loaders/test_marc_loader_comprehensive.py

"""Comprehensive tests for MarcLoader to improve coverage"""

# Standard library imports
from unittest.mock import patch
import xml.etree.ElementTree as ET

# Local imports
from marc_pd_tool.core.domain.enums import CountryClassification
from marc_pd_tool.core.domain.publication import Publication
from marc_pd_tool.infrastructure.persistence import MarcLoader


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

    def test_extract_all_batches_xml_parse_error(self, tmp_path):
        """Test handling of XML parsing errors"""
        # Create invalid XML file
        bad_xml = tmp_path / "bad.xml"
        bad_xml.write_text("This is not valid XML <unclosed")

        loader = MarcLoader(str(bad_xml))
        batches = loader.extract_all_batches()

        # Should handle error and return empty
        assert batches == []


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


class TestMarcLoaderRecordExtraction:
    """Test _extract_from_record method edge cases"""

    def test_extract_from_record_minimal(self):
        """Test extracting from minimal MARC record"""
        loader = MarcLoader("dummy.xml")

        # Create minimal record with required title field
        record = ET.fromstring(
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
        record = ET.fromstring("<record/>")  # Empty record

        # Test that exceptions in extraction return None
        pub = loader._extract_from_record(record)

        # Should return None on exception
        assert pub is None

    def test_extract_from_record_country_classification(self):
        """Test country classification extraction"""
        loader = MarcLoader("dummy.xml")

        # Create record with 008 field
        record = ET.fromstring(
            """
        <record xmlns="http://www.loc.gov/MARC21/slim">
            <controlfield tag="001">12345</controlfield>
            <controlfield tag="008">210101s1950    xxu           000 0 eng d</controlfield>
        </record>
        """
        )

        # Create record with required title
        record = ET.fromstring(
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


class TestMarcLoaderMemoryManagement:
    """Test memory management during loading"""

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


class TestMarcLoaderEdgeCases:
    """Test edge cases and error conditions"""

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

    def test_extract_marc_field_with_namespace(self):
        """Test _extract_marc_field with namespaced XML"""
        loader = MarcLoader("/dummy")

        # Create record with namespace
        record_xml = """<record xmlns="http://www.loc.gov/MARC21/slim">
            <datafield tag="264">
                <subfield code="c">1950</subfield>
            </datafield>
        </record>"""

        record = ET.fromstring(record_xml)
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

        record = ET.fromstring(record_xml)
        ns = {"marc": "http://www.loc.gov/MARC21/slim"}

        # Try 264 first, then 260
        field = loader._extract_marc_field(record, ns, ["264", "260"], "b")

        assert field is not None
        assert field.text == "Old Publisher Format"

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

        record = ET.fromstring(record_xml)
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

        record = ET.fromstring(record_xml)
        pub = loader._extract_from_record(record)

        assert pub is not None
        assert pub.title == "Main Title Part 1 The Beginning"  # Minimal cleanup only

    def test_extract_from_record_bracketed_content_removal(self):
        """Test removal of bracketed content from title"""
        loader = MarcLoader("/dummy")

        record_xml = """<record>
            <datafield tag="245">
                <subfield code="a">Test Book [microform]</subfield>
            </datafield>
        </record>"""

        record = ET.fromstring(record_xml)
        pub = loader._extract_from_record(record)

        assert pub is not None
        assert pub.title == "Test Book"  # Minimal cleanup only

    def test_extract_from_record_no_title(self):
        """Test extraction when title is missing"""
        loader = MarcLoader("/dummy")

        record_xml = """<record>
            <controlfield tag="001">001</controlfield>
            <datafield tag="100">
                <subfield code="a">Author Name</subfield>
            </datafield>
        </record>"""

        record = ET.fromstring(record_xml)
        pub = loader._extract_from_record(record)

        assert pub is None  # Should return None for missing title

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

        record = ET.fromstring(record_xml)
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

        record = ET.fromstring(record_xml)
        pub = loader._extract_from_record(record)

        assert pub is not None
        assert pub.main_author == "International Conference on Computing"  # Minimal cleanup only

    def test_extract_from_record_pub_date_from_008(self):
        """Test extracting publication date from 008 field"""
        loader = MarcLoader("/dummy")

        record_xml = """<record>
            <controlfield tag="008">210101s1955    xxu           000 0 eng d</controlfield>
            <datafield tag="245">
                <subfield code="a">Test Book</subfield>
            </datafield>
        </record>"""

        record = ET.fromstring(record_xml)
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

        record = ET.fromstring(record_xml)
        pub = loader._extract_from_record(record)

        assert pub is not None
        assert pub.language_code == "fre"

    def test_get_marc_files_non_xml_extension(self, tmp_path):
        """Test _get_marc_files with non-XML extension"""
        # Create file with .marcxml extension
        marcxml_file = tmp_path / "records.marcxml"
        marcxml_file.write_text('<?xml version="1.0"?><collection/>')

        loader = MarcLoader(str(tmp_path))
        files = loader._get_marc_files()

        assert len(files) == 1
        assert files[0].suffix == ".marcxml"
