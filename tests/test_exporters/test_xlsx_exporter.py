# tests/test_exporters/test_xlsx_exporter.py

"""Tests for XLSX export functionality"""

# Standard library imports
from os import remove
from os.path import exists
from tempfile import NamedTemporaryFile

# Third party imports
import pytest

# Local imports
from marc_pd_tool.data.enums import CopyrightStatus
from marc_pd_tool.data.enums import CountryClassification
from marc_pd_tool.data.publication import MatchResult
from marc_pd_tool.data.publication import Publication
from marc_pd_tool.exporters import XLSXExporter


@pytest.fixture
def sample_publications():
    """Create sample publications for testing"""
    # Publication with registration match
    pub1 = Publication(
        title="Test Book One",
        author="Author, Test",
        main_author="Author, Test",
        pub_date="1950",
        publisher="Test Publisher",
        place="New York",
        edition="1st ed.",
        lccn="50012345",
        language_code="eng",
        source_id="123",
        country_code="xxu",
        country_classification=CountryClassification.US,
    )
    # Set properties that are not part of the constructor
    pub1.copyright_status = CopyrightStatus.PD_NO_RENEWAL
    pub1.generic_title_detected = False
    pub1.generic_detection_reason = ""
    pub1.registration_generic_title = False
    pub1.renewal_generic_title = False
    pub1.registration_match = MatchResult(
        source_id="REG123",
        matched_title="Test Book One",
        matched_author="Author, Test",
        matched_date="1950",
        matched_publisher="Test Publisher",
        similarity_score=95.0,
        title_score=98.0,
        author_score=92.0,
        publisher_score=90.0,
        year_difference=0,
        source_type="registration",
        match_type="similarity",
    )

    # Publication with renewal match
    pub2 = Publication(
        title="Another Test Book",
        author="Writer, Another",
        main_author="Writer, Another",
        pub_date="1955",
        publisher="Another Publisher",
        place="Chicago",
        edition="",
        lccn="",
        language_code="eng",
        source_id="456",
        country_code="xxu",
        country_classification=CountryClassification.US,
    )
    # Set properties that are not part of the constructor
    pub2.copyright_status = CopyrightStatus.IN_COPYRIGHT
    pub2.generic_title_detected = False
    pub2.generic_detection_reason = ""
    pub2.registration_generic_title = False
    pub2.renewal_generic_title = False
    pub2.renewal_match = MatchResult(
        source_id="REN456",
        matched_title="Another Test Book",
        matched_author="Writer, Another",
        matched_date="1955",
        matched_publisher="",
        similarity_score=88.0,
        title_score=90.0,
        author_score=86.0,
        publisher_score=0.0,
        year_difference=0,
        source_type="renewal",
        match_type="similarity",
    )

    # Publication with no matches
    pub3 = Publication(
        title="Unknown Book",
        author="Unknown, Author",
        main_author="Unknown, Author",
        pub_date="1960",
        publisher="Unknown Publisher",
        place="London",
        edition="",
        lccn="",
        language_code="eng",
        source_id="789",
        country_code="xxk",
        country_classification=CountryClassification.NON_US,
    )
    # Set properties that are not part of the constructor
    pub3.copyright_status = CopyrightStatus.RESEARCH_US_STATUS
    pub3.generic_title_detected = False
    pub3.generic_detection_reason = ""
    pub3.registration_generic_title = False
    pub3.renewal_generic_title = False

    return [pub1, pub2, pub3]


class TestXLSXExporter:
    """Test XLSX export functionality"""

    def test_xlsx_exporter_creation(self, sample_publications):
        """Test creating XLSX exporter instance"""
        with NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            output_path = f.name

        try:
            exporter = XLSXExporter(sample_publications, output_path)
            assert exporter.publications == sample_publications
            assert exporter.output_path == output_path
            assert exporter.parameters == {}
            assert exporter.score_everything is False
        finally:
            if exists(output_path):
                remove(output_path)

    def test_xlsx_export_basic(self, sample_publications):
        """Test basic XLSX export"""
        with NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            output_path = f.name

        try:
            exporter = XLSXExporter(sample_publications, output_path)
            exporter.export()

            # Verify file was created
            assert exists(output_path)

            # Load and verify workbook structure
            # Third party imports
            from openpyxl import load_workbook

            wb = load_workbook(output_path)

            # Check sheets exist
            expected_sheets = ["Summary", "PD No Renewal", "In Copyright", "Research US Status"]
            assert set(wb.sheetnames) == set(expected_sheets)

            # Check summary sheet
            summary = wb["Summary"]
            assert summary["A1"].value == "MARC PD Tool Results Summary"
            assert summary["A4"].value == "Total Records:"
            assert summary["B4"].value == 3  # 3 sample publications

            # Check data sheets have correct headers
            pd_sheet = wb["PD No Renewal"]
            assert pd_sheet["A1"].value == "MARC ID"
            assert pd_sheet["B1"].value == "MARC Title"

            # Check data is written
            assert pd_sheet["A2"].value == "123"  # First publication ID
            assert pd_sheet["B2"].value == "Test Book One"

        finally:
            if exists(output_path):
                remove(output_path)

    def test_xlsx_export_with_parameters(self, sample_publications):
        """Test XLSX export with processing parameters"""
        with NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            output_path = f.name

        parameters = {
            "title_threshold": 40,
            "author_threshold": 30,
            "year_tolerance": 1,
            "min_year": 1950,
            "max_year": 1960,
            "us_only": True,
            "score_everything": False,
        }

        try:
            exporter = XLSXExporter(
                sample_publications, output_path, parameters, score_everything=False
            )
            exporter.export()

            # Load and verify parameters in summary
            # Third party imports
            from openpyxl import load_workbook

            wb = load_workbook(output_path)
            summary = wb["Summary"]

            # Find parameters section
            found_params = False
            for row in range(1, 30):
                if summary[f"A{row}"].value == "Parameters Used:":
                    found_params = True
                    # Check some parameters
                    assert any(
                        summary[f"A{r}"].value == "Title Threshold:"
                        for r in range(row + 1, row + 10)
                    )
                    break

            assert found_params

        finally:
            if exists(output_path):
                remove(output_path)

    def test_xlsx_data_types(self, sample_publications):
        """Test that appropriate data types are used in XLSX"""
        with NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            output_path = f.name

        try:
            exporter = XLSXExporter(sample_publications, output_path)
            exporter.export()

            # Third party imports
            from openpyxl import load_workbook

            wb = load_workbook(output_path)
            pd_sheet = wb["PD No Renewal"]

            # Check numeric types
            year_col = 13  # MARC Year column
            assert isinstance(pd_sheet.cell(row=2, column=year_col).value, int)
            assert pd_sheet.cell(row=2, column=year_col).value == 1950

            # Check float types (scores)
            reg_title_score_col = 5  # Registration Title Score
            # Note: openpyxl may store whole number floats as integers
            assert isinstance(pd_sheet.cell(row=2, column=reg_title_score_col).value, (int, float))
            assert pd_sheet.cell(row=2, column=reg_title_score_col).value == 98.0

            # Check boolean types
            generic_title_col = 32  # Generic Title Detected
            assert isinstance(pd_sheet.cell(row=2, column=generic_title_col).value, bool)
            assert pd_sheet.cell(row=2, column=generic_title_col).value is False

        finally:
            if exists(output_path):
                remove(output_path)

    def test_xlsx_column_widths(self, sample_publications):
        """Test that column widths are set appropriately"""
        with NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            output_path = f.name

        try:
            exporter = XLSXExporter(sample_publications, output_path)
            exporter.export()

            # Third party imports
            from openpyxl import load_workbook

            wb = load_workbook(output_path)
            pd_sheet = wb["PD No Renewal"]

            # Check some column widths
            assert pd_sheet.column_dimensions["A"].width == 15  # MARC ID
            assert pd_sheet.column_dimensions["B"].width == 50  # MARC Title
            assert pd_sheet.column_dimensions["M"].width == 8  # MARC Year

        finally:
            if exists(output_path):
                remove(output_path)


class TestXLSXAvailability:
    """Test XLSX availability"""

    def test_xlsx_always_available(self):
        """Test that openpyxl is available as a direct dependency"""
        # Since openpyxl is now a direct dependency, we just verify it can be imported
        try:
            # Third party imports
            pass

            assert True  # Import succeeded
        except ImportError:
            pytest.fail("openpyxl should be available as a direct dependency")

        # Also verify XLSXExporter can be imported
        # Local imports
        from marc_pd_tool.exporters import XLSXExporter as ImportedXLSXExporter

        assert ImportedXLSXExporter is not None
