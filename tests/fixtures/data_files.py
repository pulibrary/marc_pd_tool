# tests/fixtures/data_files.py

"""Shared test data file fixtures and utilities"""

# Standard library imports
from pathlib import Path
from tempfile import NamedTemporaryFile
from tempfile import TemporaryDirectory
from xml.etree import ElementTree as ET

# Third party imports
import pytest


class TestDataGenerator:
    """Generate test data files for various loaders"""

    @staticmethod
    def create_marc_xml(publications: list, include_namespace: bool = True) -> str:
        """Create a temporary MARC XML file with test data

        Args:
            publications: List of publication data dicts
            include_namespace: Whether to include MARC namespace

        Returns:
            Path to temporary MARC XML file
        """
        ns = {"": "http://www.loc.gov/MARC21/slim"} if include_namespace else {}
        root = ET.Element("collection", nsmap=ns if ns else None)

        for pub in publications:
            record = ET.SubElement(root, "record")

            # Add leader
            leader = ET.SubElement(record, "leader")
            leader.text = "00000nam a2200000 a 4500"

            # Add control field 001 (record ID)
            cf001 = ET.SubElement(record, "controlfield", tag="001")
            cf001.text = pub.get("id", "test001")

            # Add control field 008 (fixed fields including country)
            cf008 = ET.SubElement(record, "controlfield", tag="008")
            country = pub.get("country_code", "xxu")
            cf008.text = f"200101s{pub.get('year', '1950')}    {country}                 eng d"

            # Add title (245)
            df245 = ET.SubElement(record, "datafield", tag="245", ind1="1", ind2="0")
            sf245a = ET.SubElement(df245, "subfield", code="a")
            sf245a.text = pub.get("title", "Test Title")
            if pub.get("author_245c"):
                sf245c = ET.SubElement(df245, "subfield", code="c")
                sf245c.text = pub["author_245c"]

            # Add author (100)
            if pub.get("author_1xx"):
                df100 = ET.SubElement(record, "datafield", tag="100", ind1="1", ind2=" ")
                sf100a = ET.SubElement(df100, "subfield", code="a")
                sf100a.text = pub["author_1xx"]

            # Add publication info (264)
            df264 = ET.SubElement(record, "datafield", tag="264", ind1=" ", ind2="1")
            if pub.get("place"):
                sf264a = ET.SubElement(df264, "subfield", code="a")
                sf264a.text = pub["place"]
            if pub.get("publisher"):
                sf264b = ET.SubElement(df264, "subfield", code="b")
                sf264b.text = pub["publisher"]
            if pub.get("year"):
                sf264c = ET.SubElement(df264, "subfield", code="c")
                sf264c.text = pub["year"]

        # Write to temporary file
        with NamedTemporaryFile(mode="w", suffix=".xml", delete=False, encoding="utf-8") as f:
            tree = ET.ElementTree(root)
            tree.write(f.name, encoding="unicode", xml_declaration=True)
            return f.name

    @staticmethod
    def create_copyright_xml(entries: list) -> str:
        """Create a temporary copyright registration XML file

        Args:
            entries: List of copyright entry dicts

        Returns:
            Path to temporary XML file
        """
        root = ET.Element("copyrightEntries")

        for entry in entries:
            elem = ET.SubElement(root, "copyrightEntry", id=entry.get("id", "REG001"))

            title = ET.SubElement(elem, "title")
            title.text = entry.get("title", "Test Title")

            if entry.get("author"):
                author = ET.SubElement(elem, "author")
                author_name = ET.SubElement(author, "authorName")
                author_name.text = entry["author"]

            if entry.get("publisher"):
                publisher = ET.SubElement(elem, "publisher")
                publisher_name = ET.SubElement(publisher, "publisherName")
                publisher_name.text = entry["publisher"]

            if entry.get("date"):
                date = ET.SubElement(elem, "date")
                date.text = entry["date"]

        with NamedTemporaryFile(mode="w", suffix=".xml", delete=False, encoding="utf-8") as f:
            tree = ET.ElementTree(root)
            tree.write(f.name, encoding="unicode", xml_declaration=True)
            return f.name

    @staticmethod
    def create_renewal_tsv(entries: list) -> str:
        """Create a temporary renewal TSV file

        Args:
            entries: List of renewal entry dicts

        Returns:
            Path to temporary TSV file
        """
        with NamedTemporaryFile(mode="w", suffix=".tsv", delete=False, encoding="utf-8") as f:
            # Write header
            f.write("title\tauthor\toreg\todat\tid\trdat\tclaimants\n")

            # Write entries
            for entry in entries:
                row = [
                    entry.get("title", "Test Title"),
                    entry.get("author", "Test Author"),
                    entry.get("oreg", "A12345"),
                    entry.get("odat", "1950-01-01"),
                    entry.get("id", "REN001"),
                    entry.get("rdat", "1977-01-01"),
                    entry.get("claimants", "Test Claimant"),
                ]
                f.write("\t".join(row) + "\n")

            return f.name


@pytest.fixture
def test_data_generator():
    """Fixture providing the TestDataGenerator"""
    return TestDataGenerator


@pytest.fixture
def sample_marc_xml():
    """Create a sample MARC XML file for testing"""
    publications = [
        {
            "id": "test001",
            "title": "Test Book One",
            "author_245c": "by Test Author",
            "author_1xx": "Author, Test",
            "publisher": "Test Publisher",
            "place": "New York",
            "year": "1950",
            "country_code": "xxu",
        },
        {
            "id": "test002",
            "title": "Another Test Book",
            "author_245c": "by Another Writer",
            "author_1xx": "Writer, Another",
            "publisher": "Another Publisher",
            "place": "Chicago",
            "year": "1955",
            "country_code": "xxu",
        },
    ]

    xml_file = TestDataGenerator.create_marc_xml(publications)
    yield xml_file

    # Cleanup
    Path(xml_file).unlink(missing_ok=True)


@pytest.fixture
def sample_copyright_xml():
    """Create a sample copyright registration XML file"""
    entries = [
        {
            "id": "REG123",
            "title": "Test Book One",
            "author": "Author, Test",
            "publisher": "Test Publisher",
            "date": "1950",
        },
        {
            "id": "REG456",
            "title": "Another Test Book",
            "author": "Writer, Another",
            "publisher": "Another Publisher",
            "date": "1955",
        },
    ]

    xml_file = TestDataGenerator.create_copyright_xml(entries)
    yield xml_file

    # Cleanup
    Path(xml_file).unlink(missing_ok=True)


@pytest.fixture
def sample_renewal_tsv():
    """Create a sample renewal TSV file"""
    entries = [
        {
            "title": "Test Book One",
            "author": "Author, Test",
            "oreg": "A12345",
            "odat": "1950-01-01",
            "id": "REN123",
            "rdat": "1977-01-01",
            "claimants": "Test Author",
        },
        {
            "title": "Another Test Book",
            "author": "Writer, Another",
            "oreg": "A67890",
            "odat": "1955-01-01",
            "id": "REN456",
            "rdat": "1982-01-01",
            "claimants": "Another Writer",
        },
    ]

    tsv_file = TestDataGenerator.create_renewal_tsv(entries)
    yield tsv_file

    # Cleanup
    Path(tsv_file).unlink(missing_ok=True)


@pytest.fixture
def temp_data_dir():
    """Provide a temporary directory for test data files"""
    with TemporaryDirectory() as temp_dir:
        yield temp_dir
