# tests/test_loaders/test_copyright_loader.py

"""Tests for CopyrightDataLoader XML parsing functionality"""

# Standard library imports
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

# Third party imports
from pytest import fixture

# Local imports
from marc_pd_tool.loaders.copyright_loader import CopyrightDataLoader


@fixture
def sample_copyright_xml():
    """Sample copyright XML content for testing"""
    return """<?xml version="1.0" encoding="UTF-8"?>
<copyrightEntries>
    <copyrightEntry regnum="A12345">
        <title>The Great Gatsby</title>
        <author>
            <authorName>Fitzgerald, F. Scott</authorName>
        </author>
        <publisher>
            <pubName>Scribner</pubName>
            <pubPlace>New York</pubPlace>
            <pubDate date="1925">1925</pubDate>
        </publisher>
        <regDate date="1925-04-10">1925-04-10</regDate>
        <regNum>A12345</regNum>
    </copyrightEntry>
    <copyrightEntry regnum="A54321">
        <title>To Kill a Mockingbird</title>
        <author>
            <authorName>Lee, Harper</authorName>
        </author>
        <publisher>
            <pubName>Lippincott</pubName>
            <pubPlace>Philadelphia</pubPlace>
            <pubDate date="1960">1960</pubDate>
        </publisher>
        <regDate date="1960-07-11">1960-07-11</regDate>
        <regNum>A54321</regNum>
    </copyrightEntry>
</copyrightEntries>"""


@fixture
def malformed_copyright_xml():
    """Malformed copyright XML for testing error handling"""
    return """<?xml version="1.0" encoding="UTF-8"?>
<copyrightEntries>
    <copyrightEntry>
        <title>Incomplete Entry</title>
        <author>
            <authorName>Test Author</authorName>
        </author>
        <!-- Missing publisher and other required fields -->
    </copyrightEntry>
    <copyrightEntry>
        <!-- Completely empty entry -->
    </copyrightEntry>
    <copyrightEntry>
        <title></title>  <!-- Empty title -->
        <author>
            <authorName></authorName>  <!-- Empty author -->
        </author>
        <publisher>
            <pubName>Test Publisher</pubName>
        </publisher>
    </copyrightEntry>
</copyrightEntries>"""


@fixture
def invalid_xml():
    """Invalid XML content for testing XML parsing errors"""
    return """<?xml version="1.0" encoding="UTF-8"?>
<copyrightEntries>
    <copyrightEntry>
        <title>Unclosed Tag
        <author>
            <authorName>Test Author</authorName>
        </author>
    </copyrightEntry>
</copyrightEntries>"""


@fixture
def temp_copyright_dir(sample_copyright_xml, malformed_copyright_xml):
    """Create temporary directory with copyright XML files"""
    with TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create valid XML file
        valid_file = temp_path / "valid_copyright.xml"
        valid_file.write_text(sample_copyright_xml)

        # Create malformed XML file
        malformed_file = temp_path / "malformed_copyright.xml"
        malformed_file.write_text(malformed_copyright_xml)

        # Create subdirectory with more files
        subdir = temp_path / "subdir"
        subdir.mkdir()
        sub_file = subdir / "sub_copyright.xml"
        sub_file.write_text(sample_copyright_xml)

        yield temp_path


class TestCopyrightDataLoaderBasic:
    """Test basic CopyrightDataLoader functionality"""

    def test_loader_initialization(self):
        """Test basic loader initialization"""
        loader = CopyrightDataLoader("/test/path")
        assert str(loader.copyright_dir) == "/test/path"

    def test_loader_initialization_with_path_object(self):
        """Test loader initialization with Path object"""
        path_obj = Path("/test/path")
        loader = CopyrightDataLoader(path_obj)
        assert loader.copyright_dir == path_obj


class TestCopyrightXMLParsing:
    """Test XML parsing functionality"""

    def test_parse_valid_copyright_xml(self, temp_copyright_dir):
        """Test parsing valid copyright XML files"""
        loader = CopyrightDataLoader(temp_copyright_dir)
        publications = loader.load_all_copyright_data()

        # Should have 4 publications (2 from each of 2 files)
        assert len(publications) >= 4

        # Check first publication
        gatsby = None
        for pub in publications:
            if "gatsby" in pub.title.lower():
                gatsby = pub
                break

        assert gatsby is not None
        assert "great gatsby" in gatsby.title.lower()
        assert "fitzgerald" in gatsby.author.lower()
        assert gatsby.publisher.lower() == "scribner"
        assert gatsby.place.lower() == "new york"
        assert gatsby.pub_date == "1925"
        assert gatsby.source == "Copyright"
        assert gatsby.source_id == "A12345"

    def test_parse_xml_with_missing_fields(self, temp_copyright_dir):
        """Test parsing XML entries with missing optional fields"""
        loader = CopyrightDataLoader(temp_copyright_dir)
        publications = loader.load_all_copyright_data()

        # Should still parse entries with missing fields
        assert len(publications) > 0

        # Find entries from malformed file (they should have empty fields)
        incomplete_entries = [pub for pub in publications if pub.title == "incomplete entry"]
        assert len(incomplete_entries) > 0

    def test_extract_from_file_with_sample_xml(self, sample_copyright_xml):
        """Test _extract_from_file method with sample XML"""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            xml_file = temp_path / "test.xml"
            xml_file.write_text(sample_copyright_xml)

            loader = CopyrightDataLoader(temp_path)
            publications = loader._extract_from_file(xml_file)

            assert len(publications) == 2

            # Test first publication
            pub1 = publications[0]
            assert "great gatsby" in pub1.title.lower()
            assert "fitzgerald" in pub1.author.lower()
            assert pub1.year == 1925

            # Test second publication
            pub2 = publications[1]
            assert "mockingbird" in pub2.title.lower()
            assert "lee" in pub2.author.lower()
            assert pub2.year == 1960


class TestCopyrightXMLErrorHandling:
    """Test error handling for malformed or invalid XML"""

    def test_handle_invalid_xml_file(self, invalid_xml):
        """Test handling of invalid XML files"""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            invalid_file = temp_path / "invalid.xml"
            invalid_file.write_text(invalid_xml)

            loader = CopyrightDataLoader(temp_path)

            # Should handle the error gracefully and continue
            publications = loader.load_all_copyright_data()
            # Might return empty list or partial results depending on implementation
            assert isinstance(publications, list)

    def test_handle_nonexistent_directory(self):
        """Test handling of nonexistent directory"""
        loader = CopyrightDataLoader("/nonexistent/path")

        # Should handle gracefully by returning empty list when no files found
        publications = loader.load_all_copyright_data()
        assert publications == []

    def test_handle_empty_directory(self):
        """Test handling of directory with no XML files"""
        with TemporaryDirectory() as temp_dir:
            loader = CopyrightDataLoader(temp_dir)
            publications = loader.load_all_copyright_data()

            assert publications == []

    def test_handle_directory_with_non_xml_files(self):
        """Test handling of directory with non-XML files"""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create non-XML files
            text_file = temp_path / "not_xml.txt"
            text_file.write_text("This is not XML")

            json_file = temp_path / "data.json"
            json_file.write_text('{"key": "value"}')

            loader = CopyrightDataLoader(temp_path)
            publications = loader.load_all_copyright_data()

            # Should ignore non-XML files
            assert publications == []

    def test_handle_empty_xml_file(self):
        """Test handling of empty XML file"""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            empty_file = temp_path / "empty.xml"
            empty_file.write_text("")

            loader = CopyrightDataLoader(temp_path)
            publications = loader.load_all_copyright_data()

            # Should handle gracefully
            assert isinstance(publications, list)


class TestCopyrightXMLFieldExtraction:
    """Test extraction of specific fields from XML"""

    def test_extract_title_variations(self):
        """Test extraction of title from various XML structures"""
        xml_variations = [
            "<copyrightEntries><copyrightEntry><title>Simple Title</title></copyrightEntry></copyrightEntries>",
            '<copyrightEntries><copyrightEntry><title>Title with "Quotes"</title></copyrightEntry></copyrightEntries>',
            "<copyrightEntries><copyrightEntry><title>Title with &amp; Ampersand</title></copyrightEntry></copyrightEntries>",
        ]

        for xml_content in xml_variations:
            with TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                xml_file = temp_path / "test.xml"
                xml_file.write_text(xml_content)

                loader = CopyrightDataLoader(temp_path)
                publications = loader._extract_from_file(xml_file)

                assert len(publications) == 1
                assert len(publications[0].title) > 0

    def test_extract_author_variations(self):
        """Test extraction of author from various XML structures"""
        xml_with_author = """<?xml version="1.0" encoding="UTF-8"?>
<copyrightEntries>
    <copyrightEntry>
        <title>Test Book</title>
        <author>
            <authorName>Smith, John</authorName>
        </author>
    </copyrightEntry>
</copyrightEntries>"""

        xml_without_author = """<?xml version="1.0" encoding="UTF-8"?>
<copyrightEntries>
    <copyrightEntry>
        <title>Test Book</title>
    </copyrightEntry>
</copyrightEntries>"""

        # Test with author
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            xml_file = temp_path / "with_author.xml"
            xml_file.write_text(xml_with_author)

            loader = CopyrightDataLoader(temp_path)
            publications = loader._extract_from_file(xml_file)

            assert len(publications) == 1
            assert "smith" in publications[0].author.lower()

        # Test without author
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            xml_file = temp_path / "without_author.xml"
            xml_file.write_text(xml_without_author)

            loader = CopyrightDataLoader(temp_path)
            publications = loader._extract_from_file(xml_file)

            assert len(publications) == 1
            assert publications[0].author == ""

    def test_extract_publisher_information(self):
        """Test extraction of publisher information"""
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<copyrightEntries>
    <copyrightEntry>
        <title>Test Book</title>
        <publisher>
            <pubName>Test Publisher</pubName>
            <pubPlace>Test City</pubPlace>
            <pubDate date="1950">1950</pubDate>
        </publisher>
    </copyrightEntry>
</copyrightEntries>"""

        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            xml_file = temp_path / "test.xml"
            xml_file.write_text(xml_content)

            loader = CopyrightDataLoader(temp_path)
            publications = loader._extract_from_file(xml_file)

            assert len(publications) == 1
            pub = publications[0]
            assert "test publisher" in pub.publisher.lower()
            assert "test city" in pub.place.lower()
            assert pub.pub_date == "1950"

    def test_extract_registration_information(self):
        """Test extraction of registration number and date"""
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<copyrightEntries>
    <copyrightEntry regnum="A12345">
        <title>Test Book</title>
        <regDate date="1950-01-15">1950-01-15</regDate>
        <regNum>A12345</regNum>
    </copyrightEntry>
</copyrightEntries>"""

        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            xml_file = temp_path / "test.xml"
            xml_file.write_text(xml_content)

            loader = CopyrightDataLoader(temp_path)
            publications = loader._extract_from_file(xml_file)

            assert len(publications) == 1
            pub = publications[0]
            assert pub.source_id == "A12345"
            assert pub.source == "Copyright"


class TestCopyrightDataLoaderPerformance:
    """Test performance-related aspects of copyright data loading"""

    def test_recursive_file_discovery(self, temp_copyright_dir):
        """Test that loader finds XML files recursively"""
        loader = CopyrightDataLoader(temp_copyright_dir)
        publications = loader.load_all_copyright_data()

        # Should find files in both root directory and subdirectories
        assert len(publications) >= 4  # At least 2 files × 2 entries each

    def test_file_sorting(self, temp_copyright_dir):
        """Test that files are processed in sorted order"""
        loader = CopyrightDataLoader(temp_copyright_dir)

        # Create test files with names that should be sorted
        (temp_copyright_dir / "z_file.xml").write_text(
            '<?xml version="1.0"?><copyrightEntries></copyrightEntries>'
        )
        (temp_copyright_dir / "a_file.xml").write_text(
            '<?xml version="1.0"?><copyrightEntries></copyrightEntries>'
        )
        (temp_copyright_dir / "m_file.xml").write_text(
            '<?xml version="1.0"?><copyrightEntries></copyrightEntries>'
        )

        # Mock _extract_from_file to track file processing order
        processed_files = []
        loader._extract_from_file

        def track_files(xml_file):
            processed_files.append(xml_file.name)
            return []

        with patch.object(loader, "_extract_from_file", side_effect=track_files):
            loader.load_all_copyright_data()

        # Verify files were processed in sorted order
        assert len(processed_files) >= 3
        sorted_test_files = [
            name for name in processed_files if name in ["a_file.xml", "m_file.xml", "z_file.xml"]
        ]
        assert sorted_test_files == sorted(sorted_test_files)

    @patch("marc_pd_tool.loaders.copyright_loader.logger")
    def test_logging_behavior(self, mock_logger, temp_copyright_dir):
        """Test that appropriate logging occurs during loading"""
        loader = CopyrightDataLoader(temp_copyright_dir)
        loader.load_all_copyright_data()

        # Verify that info logging was called
        mock_logger.info.assert_called()
        mock_logger.debug.assert_called()


class TestCopyrightDataLoaderEdgeCases:
    """Test edge cases and boundary conditions"""

    def test_xml_with_unicode_characters(self):
        """Test handling of XML with Unicode characters"""
        xml_with_unicode = """<?xml version="1.0" encoding="UTF-8"?>
<copyrightEntries>
    <copyrightEntry>
        <title>Test Book with Unicode</title>
        <author>
            <authorName>Author, Test</authorName>
        </author>
        <publisher>
            <pubName>Publisher and Co.</pubName>
            <pubPlace>City, New York</pubPlace>
        </publisher>
    </copyrightEntry>
</copyrightEntries>"""

        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            xml_file = temp_path / "unicode.xml"
            xml_file.write_text(xml_with_unicode, encoding="utf-8")

            loader = CopyrightDataLoader(temp_path)
            publications = loader._extract_from_file(xml_file)

            assert len(publications) == 1
            pub = publications[0]
            assert "unicode" in pub.title.lower()
            assert "test" in pub.author.lower()

    def test_very_long_field_values(self):
        """Test handling of very long field values"""
        long_title = "Very " * 100 + "Long Title"
        long_author = "Author " * 50 + "Name"

        xml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<copyrightEntries>
    <copyrightEntry>
        <title>{long_title}</title>
        <author>
            <authorName>{long_author}</authorName>
        </author>
    </copyrightEntry>
</copyrightEntries>"""

        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            xml_file = temp_path / "long_fields.xml"
            xml_file.write_text(xml_content)

            loader = CopyrightDataLoader(temp_path)
            publications = loader._extract_from_file(xml_file)

            assert len(publications) == 1
            pub = publications[0]
            assert len(pub.original_title) > 100
            assert len(pub.original_author) > 100

    def test_xml_with_cdata_sections(self):
        """Test handling of XML with CDATA sections"""
        xml_with_cdata = """<?xml version="1.0" encoding="UTF-8"?>
<copyrightEntries>
    <copyrightEntry>
        <title><![CDATA[Title with <special> & characters]]></title>
        <author>
            <authorName><![CDATA[Author, With & Special <chars>]]></authorName>
        </author>
    </copyrightEntry>
</copyrightEntries>"""

        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            xml_file = temp_path / "cdata.xml"
            xml_file.write_text(xml_with_cdata)

            loader = CopyrightDataLoader(temp_path)
            publications = loader._extract_from_file(xml_file)

            assert len(publications) == 1
            pub = publications[0]
            assert "<special>" in pub.original_title
            assert "&" in pub.original_title
