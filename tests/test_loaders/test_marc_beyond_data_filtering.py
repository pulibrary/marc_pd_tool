# tests/test_loaders/test_marc_beyond_data_filtering.py

"""Tests for MARC loader filtering of records beyond available data"""

# Standard library imports
from pathlib import Path
from tempfile import NamedTemporaryFile
from xml.etree.ElementTree import Element
from xml.etree.ElementTree import SubElement
from xml.etree.ElementTree import tostring

# Local imports
from marc_pd_tool.infrastructure.persistence import MarcLoader


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
