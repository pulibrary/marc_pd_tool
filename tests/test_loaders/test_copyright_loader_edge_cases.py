# tests/test_loaders/test_copyright_loader_edge_cases.py

"""Edge case tests for CopyrightDataLoader to achieve 100% coverage"""

# Standard library imports
import xml.etree.ElementTree as ET

# Third party imports
import pytest

# Local imports
from marc_pd_tool.loaders.copyright_loader import CopyrightDataLoader


class TestCopyrightLoaderEdgeCases:
    """Test edge cases and uncovered paths in CopyrightDataLoader"""

    def test_extract_year_from_filename(self):
        """Test year extraction from filename"""
        loader = CopyrightDataLoader("/dummy")

        # Test various filename patterns - note: \b requires word boundaries
        assert loader._extract_year_from_filename("reg 1950.xml") == "1950"
        assert loader._extract_year_from_filename("file-2023-data.xml") == "2023"
        assert loader._extract_year_from_filename("no_year_here.xml") == ""
        assert loader._extract_year_from_filename("copyright 1923.xml") == "1923"
        assert loader._extract_year_from_filename("2001-records.xml") == "2001"
        assert loader._extract_year_from_filename("data.1955.xml") == "1955"

    def test_extract_from_file_empty_root(self, tmp_path):
        """Test parsing XML with empty root element"""
        loader = CopyrightDataLoader(str(tmp_path))

        # Create XML with empty root
        xml_content = '<?xml version="1.0"?><copyrightEntries/>'
        xml_file = tmp_path / "empty.xml"
        xml_file.write_text(xml_content)

        publications = loader._extract_from_file(xml_file)

        assert publications == []

    def test_extract_from_file_malformed(self, tmp_path):
        """Test parsing malformed XML file"""
        loader = CopyrightDataLoader(str(tmp_path))

        # Create malformed XML
        xml_file = tmp_path / "malformed.xml"
        xml_file.write_text("This is not XML")

        publications = loader._extract_from_file(xml_file)

        # Should handle error and return empty list
        assert publications == []

    def test_extract_from_entry_missing_fields(self):
        """Test parsing entry with missing fields"""
        loader = CopyrightDataLoader("/dummy")

        # Entry with minimal fields
        entry_xml = """<copyrightEntry>
            <title>Minimal Entry</title>
        </copyrightEntry>"""

        entry = ET.fromstring(entry_xml)
        pub = loader._extract_from_entry(entry)

        assert pub is not None
        assert pub.title == "minimal entry"  # Title normalized to lowercase
        assert pub.author == ""
        assert pub.publisher == ""

    def test_extract_from_entry_no_title(self):
        """Test parsing entry with no title"""
        loader = CopyrightDataLoader("/dummy")

        # Entry without title
        entry_xml = """<copyrightEntry>
            <author>
                <authorName>Author Name</authorName>
            </author>
        </copyrightEntry>"""

        entry = ET.fromstring(entry_xml)
        pub = loader._extract_from_entry(entry)

        # Should return None for missing title
        assert pub is None

    def test_extract_from_entry_date_sources(self):
        """Test extracting dates from different sources"""
        loader = CopyrightDataLoader("/dummy")

        # Test pubDate
        entry_xml1 = """<copyrightEntry>
            <title>Book 1</title>
            <publisher>
                <pubDate date="1950-12-31"/>
            </publisher>
        </copyrightEntry>"""

        entry1 = ET.fromstring(entry_xml1)
        pub1 = loader._extract_from_entry(entry1)
        assert pub1.pub_date == "1950-12-31"
        assert pub1.year == 1950

        # Test regDate when no pubDate
        entry_xml2 = """<copyrightEntry>
            <title>Book 2</title>
            <regDate date="1955-06-15"/>
        </copyrightEntry>"""

        entry2 = ET.fromstring(entry_xml2)
        pub2 = loader._extract_from_entry(entry2)
        assert pub2.pub_date == "1955-06-15"
        assert pub2.year == 1955

        # Test affDate when no pubDate or regDate
        entry_xml3 = """<copyrightEntry>
            <title>Book 3</title>
            <affDate date="1960-01-01"/>
        </copyrightEntry>"""

        entry3 = ET.fromstring(entry_xml3)
        pub3 = loader._extract_from_entry(entry3)
        assert pub3.pub_date == "1960-01-01"
        assert pub3.year == 1960

        # Test with text content instead of date attribute
        entry_xml4 = """<copyrightEntry>
            <title>Book 4</title>
            <publisher>
                <pubDate>1965</pubDate>
            </publisher>
        </copyrightEntry>"""

        entry4 = ET.fromstring(entry_xml4)
        pub4 = loader._extract_from_entry(entry4)
        assert pub4.pub_date == "1965"
        assert pub4.year == 1965

    def test_load_all_copyright_data_empty_directory(self, tmp_path):
        """Test loading from empty directory"""
        loader = CopyrightDataLoader(str(tmp_path))

        publications = loader.load_all_copyright_data()

        assert publications == []

    def test_load_all_copyright_data_with_subdirectories(self, tmp_path):
        """Test loading with nested year subdirectories"""
        # Create year subdirectories
        for year in [1950, 1951]:
            year_dir = tmp_path / str(year)
            year_dir.mkdir()

            # Create XML file in each
            xml_content = f"""<?xml version="1.0"?>
            <copyrightEntries>
                <copyrightEntry>
                    <title>Book from {year}</title>
                    <regDate date="{year}-01-01"/>
                </copyrightEntry>
            </copyrightEntries>"""

            (year_dir / "entries.xml").write_text(xml_content)

        loader = CopyrightDataLoader(str(tmp_path))
        publications = loader.load_all_copyright_data()

        assert len(publications) == 2
        titles = [pub.title for pub in publications]
        assert "book from 1950" in titles  # Title normalized to lowercase
        assert "book from 1951" in titles

    def test_load_all_copyright_data_year_filtered(self, tmp_path):
        """Test year filtering with edge cases"""
        # Create publications across years
        for year in range(1948, 1953):
            year_dir = tmp_path / str(year)
            year_dir.mkdir()

            xml_content = f"""<?xml version="1.0"?>
            <copyrightEntries>
                <copyrightEntry>
                    <title>Book {year}</title>
                    <regDate date="{year}-01-01"/>
                </copyrightEntry>
            </copyrightEntries>"""

            (year_dir / "entries.xml").write_text(xml_content)

        loader = CopyrightDataLoader(str(tmp_path))

        # Test exact boundaries
        pubs = loader.load_all_copyright_data(min_year=1950, max_year=1950)
        assert len(pubs) == 1
        assert pubs[0].year == 1950

        # Test with buffer
        pubs = loader.load_all_copyright_data(min_year=1949, max_year=1951)
        assert len(pubs) == 3  # 1949, 1950, 1951

        # Test min only
        pubs = loader.load_all_copyright_data(min_year=1951)
        assert len(pubs) == 2  # 1951, 1952

        # Test max only
        pubs = loader.load_all_copyright_data(max_year=1949)
        assert len(pubs) == 2  # 1948, 1949


class TestCopyrightLoaderSpecialCases:
    """Test special cases and complex scenarios"""

    def test_extract_from_entry_unicode_handling(self):
        """Test handling of Unicode characters in entries"""
        loader = CopyrightDataLoader("/dummy")

        # Create entry with Unicode
        entry_xml = """<copyrightEntry id="REG123">
            <title>La Bibliothèque française</title>
            <author>
                <authorName>René Descartes</authorName>
            </author>
            <publisher>
                <pubName>Éditions Gallimard</pubName>
            </publisher>
        </copyrightEntry>"""

        entry = ET.fromstring(entry_xml)
        pub = loader._extract_from_entry(entry)

        assert (
            pub.title == "la bibliotheque francaise"
        )  # Title normalized to lowercase and ASCII folded
        assert pub.author == "rene descartes"  # Author normalized to lowercase and ASCII folded
        assert (
            pub.publisher == "editions gallimard"
        )  # Publisher normalized to lowercase and ASCII folded

    def test_extract_from_entry_special_characters(self):
        """Test handling of special XML characters"""
        loader = CopyrightDataLoader("/dummy")

        # Entry with escaped characters
        entry_xml = """<copyrightEntry regnum="A123">
            <title>Title &amp; Subtitle</title>
            <author>
                <authorName>Author &lt;Name&gt;</authorName>
            </author>
        </copyrightEntry>"""

        entry = ET.fromstring(entry_xml)
        pub = loader._extract_from_entry(entry)

        assert pub.title == "title subtitle"  # Title normalized, punctuation removed
        assert pub.author == "author name"  # Author normalized, special chars removed
        assert pub.source_id == "A123"

    def test_extract_from_entry_volume_handling(self):
        """Test handling of volume information"""
        loader = CopyrightDataLoader("/dummy")

        # Entry with volume information
        entry_xml = """<copyrightEntry>
            <title>Encyclopedia</title>
            <vol>Volume 3</vol>
        </copyrightEntry>"""

        entry = ET.fromstring(entry_xml)
        pub = loader._extract_from_entry(entry)

        # Volume should be appended to title
        assert pub.title == "encyclopedia volume 3"  # Title normalized to lowercase

    def test_load_all_copyright_data_with_parse_errors(self, tmp_path):
        """Test load_all continues despite individual file errors"""
        # Create mix of valid and invalid files
        year_dir = tmp_path / "1950"
        year_dir.mkdir()

        # Valid file
        valid_xml = """<?xml version="1.0"?>
        <copyrightEntries>
            <copyrightEntry>
                <title>Valid Book</title>
            </copyrightEntry>
        </copyrightEntries>"""
        (year_dir / "valid.xml").write_text(valid_xml)

        # Invalid file
        (year_dir / "invalid.xml").write_text("Not XML at all")

        loader = CopyrightDataLoader(str(tmp_path))
        publications = loader.load_all_copyright_data()

        # Should load the valid file despite error in invalid file
        assert len(publications) == 1
        assert publications[0].title == "valid book"  # Title normalized to lowercase

    def test_get_year_range(self, tmp_path):
        """Test getting year range from copyright data"""
        loader = CopyrightDataLoader(str(tmp_path))

        # Empty directory
        min_year, max_year = loader.get_year_range()
        assert min_year is None
        assert max_year is None

        # Create XML files with year data
        for year in [1945, 1965]:
            year_dir = tmp_path / str(year)
            year_dir.mkdir()

            xml_content = f"""<?xml version="1.0"?>
            <copyrightEntries>
                <copyrightEntry>
                    <title>Book {year}</title>
                    <regDate date="{year}-01-01"/>
                </copyrightEntry>
                <copyrightEntry>
                    <title>Book {year} B</title>
                    <publisher>
                        <pubDate date="{year}-06-01"/>
                    </publisher>
                </copyrightEntry>
            </copyrightEntries>"""

            (year_dir / "entries.xml").write_text(xml_content)

        min_year, max_year = loader.get_year_range()
        assert min_year == 1945
        assert max_year == 1965

    def test_extract_year_from_entry(self):
        """Test year extraction from entry"""
        loader = CopyrightDataLoader("/dummy")

        # Test with pubDate
        entry_xml1 = """<copyrightEntry>
            <publisher>
                <pubDate date="1950-01-01"/>
            </publisher>
        </copyrightEntry>"""
        entry1 = ET.fromstring(entry_xml1)
        year1 = loader._extract_year_from_entry(entry1)
        assert year1 == 1950

        # Test with regDate
        entry_xml2 = """<copyrightEntry>
            <regDate date="1960"/>
        </copyrightEntry>"""
        entry2 = ET.fromstring(entry_xml2)
        year2 = loader._extract_year_from_entry(entry2)
        assert year2 == 1960

        # Test with no date
        entry_xml3 = """<copyrightEntry>
            <title>No Date Book</title>
        </copyrightEntry>"""
        entry3 = ET.fromstring(entry_xml3)
        year3 = loader._extract_year_from_entry(entry3)
        assert year3 is None

    def test_extract_from_entry_lccn(self):
        """Test LCCN extraction"""
        loader = CopyrightDataLoader("/dummy")

        entry_xml = """<copyrightEntry>
            <title>Book with LCCN</title>
            <lccn>   55012345   </lccn>
        </copyrightEntry>"""

        entry = ET.fromstring(entry_xml)
        pub = loader._extract_from_entry(entry)

        assert pub.lccn == "   55012345   "  # LCCN not stripped in extraction
