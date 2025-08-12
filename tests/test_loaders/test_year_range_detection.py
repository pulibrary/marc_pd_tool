# tests/test_loaders/test_year_range_detection.py

"""Tests for year range detection in copyright and renewal loaders"""

# Standard library imports
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

# Local imports
from marc_pd_tool.loaders.copyright_loader import CopyrightDataLoader
from marc_pd_tool.loaders.renewal_loader import RenewalDataLoader


class TestYearRangeDetection(TestCase):
    """Test year range detection functionality"""

    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

    def tearDown(self):
        """Clean up test fixtures"""
        self.temp_dir.cleanup()

    def test_copyright_year_range_detection(self):
        """Test copyright data year range detection"""
        # Create test XML file with various date formats
        test_xml = """<?xml version="1.0" encoding="UTF-8"?>
<copyrightEntries>
    <copyrightEntry id="test1">
        <title>Early Work</title>
        <author><authorName>Smith, John</authorName></author>
        <publisher>
            <pubDate date="1923">1923</pubDate>
            <pubName>Test Publisher</pubName>
        </publisher>
    </copyrightEntry>
    <copyrightEntry id="test2">
        <title>Middle Work</title>
        <author><authorName>Doe, Jane</authorName></author>
        <regDate date="1950-05-15">1950-05-15</regDate>
    </copyrightEntry>
    <copyrightEntry id="test3">
        <title>Late Work</title>
        <author><authorName>Brown, Bob</authorName></author>
        <affDate date="1977-12-31">1977-12-31</affDate>
    </copyrightEntry>
    <copyrightEntry id="test4">
        <title>Invalid Date Work</title>
        <author><authorName>Green, Grace</authorName></author>
        <publisher>
            <pubDate>invalid-date</pubDate>
        </publisher>
    </copyrightEntry>
</copyrightEntries>"""

        # Write test file
        test_file = self.temp_path / "test_copyright.xml"
        test_file.write_text(test_xml)

        # Test year range detection
        loader = CopyrightDataLoader(str(self.temp_path))
        min_year, max_year = loader.year_range

        # Verify results
        self.assertEqual(min_year, 1923)
        self.assertEqual(max_year, 1977)

    def test_copyright_year_range_empty_directory(self):
        """Test copyright year range detection with empty directory"""
        loader = CopyrightDataLoader(str(self.temp_path))
        min_year, max_year = loader.year_range

        self.assertIsNone(min_year)
        self.assertIsNone(max_year)

    def test_copyright_year_range_no_valid_years(self):
        """Test copyright year range detection with no valid years"""
        test_xml = """<?xml version="1.0" encoding="UTF-8"?>
<copyrightEntries>
    <copyrightEntry id="test1">
        <title>No Date Work</title>
        <author><authorName>Smith, John</authorName></author>
    </copyrightEntry>
</copyrightEntries>"""

        test_file = self.temp_path / "test_copyright.xml"
        test_file.write_text(test_xml)

        loader = CopyrightDataLoader(str(self.temp_path))
        min_year, max_year = loader.year_range

        self.assertIsNone(min_year)
        self.assertIsNone(max_year)

    def test_renewal_year_range_detection(self):
        """Test renewal data year range detection"""
        # Create test TSV file
        test_tsv = """id	title	author	oreg	odat	rdat	claimants	entry_id
R123456	Early Renewal	Smith, John	A12345	1925-01-01	1952-06-15	Smith Estate	uuid-1234
R789012	Middle Renewal	Doe, Jane	B67890	1940-03-10	1967-11-20	Doe Publishing	uuid-5678
R345678	Late Renewal	Brown, Bob	C34567	1965-12-25	1993-07-04	Brown Inc	uuid-9012
R999999	Invalid Date	Green, Grace	D99999	invalid-date	2000-01-01	Green LLC	uuid-0000"""

        # Write test file
        test_file = self.temp_path / "test_renewal.tsv"
        test_file.write_text(test_tsv)

        # Test year range detection
        loader = RenewalDataLoader(str(self.temp_path))
        min_year, max_year = loader.year_range

        # Verify results (based on odat field)
        self.assertEqual(min_year, 1925)
        self.assertEqual(max_year, 1965)

    def test_renewal_year_range_empty_directory(self):
        """Test renewal year range detection with empty directory"""
        loader = RenewalDataLoader(str(self.temp_path))
        min_year, max_year = loader.year_range

        self.assertIsNone(min_year)
        self.assertIsNone(max_year)

    def test_renewal_year_range_no_valid_years(self):
        """Test renewal year range detection with no valid years"""
        test_tsv = """id	title	author	oreg	odat	rdat	claimants	entry_id
R123456	No Date Work	Smith, John	A12345		1952-06-15	Smith Estate	uuid-1234"""

        test_file = self.temp_path / "test_renewal.tsv"
        test_file.write_text(test_tsv)

        loader = RenewalDataLoader(str(self.temp_path))
        min_year, max_year = loader.year_range

        self.assertIsNone(min_year)
        self.assertIsNone(max_year)

    def test_copyright_extract_year_from_entry(self):
        """Test individual year extraction from copyright entries"""
        test_xml = """<?xml version="1.0" encoding="UTF-8"?>
<copyrightEntries>
    <copyrightEntry id="test1">
        <title>Test Work</title>
        <publisher>
            <pubDate date="1945">1945</pubDate>
        </publisher>
    </copyrightEntry>
</copyrightEntries>"""

        test_file = self.temp_path / "test.xml"
        test_file.write_text(test_xml)

        loader = CopyrightDataLoader(str(self.temp_path))

        # Parse the entry and test extraction
        # Standard library imports
        import xml.etree.ElementTree as ET

        tree = ET.parse(test_file)
        root = tree.getroot()
        entry = root.find(".//copyrightEntry")

        year = loader._extract_year_from_entry(entry)
        self.assertEqual(year, 1945)

    def test_renewal_extract_year_from_row(self):
        """Test individual year extraction from renewal rows"""
        loader = RenewalDataLoader(str(self.temp_path))

        # Test valid row
        row = {"odat": "1943-05-10", "title": "Test Work", "author": "Test Author"}
        year = loader._extract_year_from_row(row)
        self.assertEqual(year, 1943)

        # Test invalid row
        row = {"odat": "invalid", "title": "Test Work", "author": "Test Author"}
        year = loader._extract_year_from_row(row)
        self.assertIsNone(year)

        # Test empty row
        row = {"odat": "", "title": "Test Work", "author": "Test Author"}
        year = loader._extract_year_from_row(row)
        self.assertIsNone(year)
