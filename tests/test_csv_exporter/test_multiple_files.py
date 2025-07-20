"""Tests for multiple CSV file output functionality"""

# Standard library imports
from csv import reader
from os import unlink
from os.path import exists
from os.path import splitext
from tempfile import NamedTemporaryFile

# Local imports
from marc_pd_tool.csv_exporter import save_matches_csv
from marc_pd_tool.enums import CopyrightStatus
from marc_pd_tool.enums import CountryClassification
from marc_pd_tool.publication import Publication

# pytest imported automatically by test runner


class TestCSVMultipleFiles:
    """Test multiple CSV file output by copyright status"""

    def test_csv_output_multiple_files_by_status(self):
        """Test that CSV output creates separate files by copyright status"""
        # Create publications with different copyright statuses
        pub1 = Publication(
            title="PD Book",
            author="PD Author",
            pub_date="1950",
            source_id="test_001",
            country_classification=CountryClassification.US,
        )
        pub1.copyright_status = CopyrightStatus.PD_NO_RENEWAL

        pub2 = Publication(
            title="In Copyright Book",
            author="IC Author",
            pub_date="1960",
            source_id="test_002",
            country_classification=CountryClassification.US,
        )
        pub2.copyright_status = CopyrightStatus.IN_COPYRIGHT

        pub3 = Publication(
            title="Research Book",
            author="Research Author",
            pub_date="1955",
            source_id="test_003",
            country_classification=CountryClassification.US,
        )
        pub3.copyright_status = CopyrightStatus.RESEARCH_US_STATUS

        publications = [pub1, pub2, pub3]

        with NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            temp_file = f.name

        try:
            # Use default behavior (multiple files)
            save_matches_csv(publications, temp_file, single_file=False)

            # Check that separate files were created
            base_name, ext = splitext(temp_file)

            pd_file = f"{base_name}_pd_no_renewal{ext}"
            ic_file = f"{base_name}_in_copyright{ext}"
            research_file = f"{base_name}_research_us_status{ext}"

            assert exists(pd_file), f"PD file should exist: {pd_file}"
            assert exists(ic_file), f"In Copyright file should exist: {ic_file}"
            assert exists(research_file), f"Research file should exist: {research_file}"

            # Check content of each file
            with open(pd_file, "r") as f:
                pd_lines = f.readlines()
            assert len(pd_lines) == 2, "PD file should have header + 1 record"
            assert "PD Book" in pd_lines[1]

            with open(ic_file, "r") as f:
                ic_lines = f.readlines()
            assert len(ic_lines) == 2, "In Copyright file should have header + 1 record"
            assert "In Copyright Book" in ic_lines[1]

            with open(research_file, "r") as f:
                research_lines = f.readlines()
            assert len(research_lines) == 2, "Research file should have header + 1 record"
            assert "Research Book" in research_lines[1]

            # Clean up individual files
            unlink(pd_file)
            unlink(ic_file)
            unlink(research_file)

        finally:
            # The original temp_file might not exist in multi-file mode
            try:
                unlink(temp_file)
            except FileNotFoundError:
                pass

    def test_csv_column_order_groups_related_fields(self):
        """Test that CSV columns are properly grouped by type"""
        pub = Publication(
            title="Test Book",
            author="Test Author",
            pub_date="1950",
            source_id="test_001",
            country_classification=CountryClassification.US,
        )

        with NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            temp_file = f.name

        try:
            save_matches_csv([pub], temp_file, single_file=True)

            with open(temp_file, "r") as f:
                headers = f.readline().strip().split(",")

            # Check that related fields are grouped together
            title_indices = [
                headers.index("MARC Title"),
                headers.index("Registration Title"),
                headers.index("Renewal Title"),
                headers.index("Registration Title Score"),
                headers.index("Renewal Title Score"),
            ]

            author_indices = [
                headers.index("MARC Author"),
                headers.index("Registration Author"),
                headers.index("Renewal Author"),
                headers.index("Registration Author Score"),
                headers.index("Renewal Author Score"),
            ]

            # Title fields should be grouped together and appear before author fields
            assert title_indices == sorted(title_indices), "Title fields should be consecutive"
            assert author_indices == sorted(author_indices), "Author fields should be consecutive"
            assert max(title_indices) < min(
                author_indices
            ), "Title fields should come before author fields"

        finally:
            unlink(temp_file)

    def test_single_file_flag_creates_single_output(self):
        """Test that single_file=True creates a single output file with all records"""
        pub1 = Publication(
            title="Book 1",
            author="Author 1",
            pub_date="1950",
            source_id="test_001",
            country_classification=CountryClassification.US,
        )
        pub1.copyright_status = CopyrightStatus.PD_NO_RENEWAL

        pub2 = Publication(
            title="Book 2",
            author="Author 2",
            pub_date="1960",
            source_id="test_002",
            country_classification=CountryClassification.US,
        )
        pub2.copyright_status = CopyrightStatus.IN_COPYRIGHT

        publications = [pub1, pub2]

        with NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            temp_file = f.name

        try:
            # Use legacy behavior (single file)
            save_matches_csv(publications, temp_file, single_file=True)

            # Check that only the original file exists
            assert exists(temp_file), f"Single file should exist: {temp_file}"

            # Check that it contains both records
            with open(temp_file, "r") as f:
                lines = f.readlines()

            assert len(lines) == 3, "Single file should have header + 2 records"
            content = "".join(lines)
            assert "Book 1" in content
            assert "Book 2" in content

            # Check that no separate status files were created
            base_name, ext = splitext(temp_file)
            pd_file = f"{base_name}_pd_no_renewal{ext}"
            ic_file = f"{base_name}_in_copyright{ext}"

            assert not exists(pd_file), "Separate PD file should not exist in single file mode"
            assert not exists(ic_file), "Separate IC file should not exist in single file mode"

        finally:
            unlink(temp_file)
