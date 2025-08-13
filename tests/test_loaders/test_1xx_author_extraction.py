# tests/test_loaders/test_1xx_author_extraction.py

"""Test extraction of 1xx author fields from MARC records"""

# Standard library imports
import xml.etree.ElementTree as ET

# Local imports
from marc_pd_tool.infrastructure.persistence import MarcLoader


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

        record = ET.fromstring(xml_string)
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

        record = ET.fromstring(xml_string)
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

        record = ET.fromstring(xml_string)
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

        record = ET.fromstring(xml_string)
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

        record = ET.fromstring(xml_string)
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

        record = ET.fromstring(xml_string)
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

        record = ET.fromstring(xml_string)
        pub = extractor._extract_from_record(record)

        assert pub is not None
        assert pub.original_author == "by Dr. Mary Johnson."
        assert pub.original_main_author == "Johnson, Mary"  # Date cleaned
