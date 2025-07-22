"""Test volume/part extraction from copyright registration data"""

# Standard library imports
import xml.etree.ElementTree as ET

# Local imports
from marc_pd_tool.loaders.copyright_loader import CopyrightDataLoader


class TestVolumeExtraction:
    """Test extraction of volume information from copyright XML"""

    def test_vol_tag_extraction(self):
        """Test extraction of volume info from <vol> tags"""
        loader = CopyrightDataLoader("dummy_path")

        # Create test XML entry with volume
        xml_string = """
        <copyrightEntry id="test" regnum="A593951">
            <title>Advances in geophysics</title>
            <vol>Vol.17</vol>
            <author><authorName>H. E. Landsberg</authorName></author>
            <publisher>
                <pubName>Academic Press, Inc.</pubName>
                <pubDate date="1974">1974</pubDate>
            </publisher>
        </copyrightEntry>
        """

        entry = ET.fromstring(xml_string)
        pub = loader._extract_from_entry(entry)

        assert pub is not None
        assert pub.original_title == "Advances in geophysics"
        assert pub.original_part_number == "17"  # Should extract the number
        assert pub.original_part_name is None  # No part name in this format

    def test_different_vol_formats(self):
        """Test different volume tag formats"""
        loader = CopyrightDataLoader("dummy_path")

        # Test Vol.3 format
        xml_string1 = """
        <copyrightEntry id="test1" regnum="A593951">
            <title>Test Book</title>
            <vol>Vol.3</vol>
        </copyrightEntry>
        """
        entry1 = ET.fromstring(xml_string1)
        pub1 = loader._extract_from_entry(entry1)
        assert pub1.original_part_number == "3"

        # Test Volume 5 format
        xml_string2 = """
        <copyrightEntry id="test2" regnum="A593952">
            <title>Test Book</title>
            <vol>Volume 5</vol>
        </copyrightEntry>
        """
        entry2 = ET.fromstring(xml_string2)
        pub2 = loader._extract_from_entry(entry2)
        assert pub2.original_part_number == "5"

        # Test other format
        xml_string3 = """
        <copyrightEntry id="test3" regnum="A593953">
            <title>Test Book</title>
            <vol>Part A</vol>
        </copyrightEntry>
        """
        entry3 = ET.fromstring(xml_string3)
        pub3 = loader._extract_from_entry(entry3)
        assert pub3.original_part_number == "Part A"

    def test_no_vol_tag(self):
        """Test that entries without volume tags work normally"""
        loader = CopyrightDataLoader("dummy_path")

        xml_string = """
        <copyrightEntry id="test" regnum="A593951">
            <title>Simple Book</title>
            <author><authorName>Author Name</authorName></author>
        </copyrightEntry>
        """

        entry = ET.fromstring(xml_string)
        pub = loader._extract_from_entry(entry)

        assert pub is not None
        assert pub.original_title == "Simple Book"
        assert pub.original_part_number is None
        assert pub.original_part_name is None
