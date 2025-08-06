# tests/test_exporters/test_multiple_files.py

"""Tests for multiple CSV file output functionality"""

# Standard library imports
from os import unlink
from os.path import exists
from os.path import splitext
from pathlib import Path
from shutil import rmtree
from tempfile import NamedTemporaryFile

# Local imports
from marc_pd_tool.data.publication import CopyrightStatus
from marc_pd_tool.data.publication import CountryClassification
from marc_pd_tool.data.publication import Publication
from marc_pd_tool.exporters.csv_exporter import CSVExporter
from marc_pd_tool.exporters.json_exporter import save_matches_json


def export_to_csv(publications, csv_file, single_file=True):
    """Helper to export publications to CSV via JSON"""
    # Standard library imports
    import os
    import tempfile

    if single_file:
        # For single file, standard approach
        temp_fd, temp_json = tempfile.mkstemp(suffix=".json")
        os.close(temp_fd)

        try:
            save_matches_json(publications, temp_json)
            exporter = CSVExporter(temp_json, csv_file, single_file=True)
            exporter.export()
        finally:
            if os.path.exists(temp_json):
                os.unlink(temp_json)
    else:
        # For multiple files, the new CSVExporter expects a single JSON
        # and creates multiple CSV files from it
        temp_fd, temp_json = tempfile.mkstemp(suffix=".json")
        os.close(temp_fd)

        try:
            # Create single JSON with all publications
            save_matches_json(publications, temp_json)
            # CSVExporter will split by status when single_file=False
            exporter = CSVExporter(temp_json, csv_file, single_file=False)
            exporter.export()
        finally:
            if os.path.exists(temp_json):
                os.unlink(temp_json)


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
        pub1.copyright_status = CopyrightStatus.US_REGISTERED_NOT_RENEWED.value

        pub2 = Publication(
            title="In Copyright Book",
            author="IC Author",
            pub_date="1960",
            source_id="test_002",
            country_classification=CountryClassification.US,
        )
        pub2.copyright_status = CopyrightStatus.US_RENEWED.value

        pub3 = Publication(
            title="Research Book",
            author="Research Author",
            pub_date="1955",
            source_id="test_003",
            country_classification=CountryClassification.US,
        )
        pub3.copyright_status = CopyrightStatus.US_NO_MATCH.value

        publications = [pub1, pub2, pub3]

        with NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            temp_file = f.name

        try:
            # Use default behavior (folder structure)
            export_to_csv(publications, temp_file, single_file=False)

            # Check that folder structure was created
            base_name = Path(temp_file).stem
            parent_dir = Path(temp_file).parent
            csv_dir = parent_dir / f"{base_name}_csv"

            assert csv_dir.exists(), f"CSV directory should exist: {csv_dir}"

            # Check for summary file
            summary_file = csv_dir / "_summary.csv"
            assert summary_file.exists(), f"Summary file should exist: {summary_file}"

            # File names based on formatted status values
            pd_file = csv_dir / "us_registered_not_renewed.csv"
            ic_file = csv_dir / "us_renewed.csv"
            research_file = csv_dir / "us_no_match.csv"

            assert pd_file.exists(), f"PD file should exist: {pd_file}"
            assert ic_file.exists(), f"In Copyright file should exist: {ic_file}"
            assert research_file.exists(), f"Research file should exist: {research_file}"

            # Check content of each file
            with open(pd_file, "r") as f:
                pd_lines = f.readlines()
            assert len(pd_lines) == 2, "PD file should have header + 1 record"
            assert "PD Book" in pd_lines[1]

            # Check summary file
            with open(summary_file, "r") as f:
                summary_lines = f.readlines()
            assert len(summary_lines) >= 4, "Summary should have header + status rows + total"
            assert "Status,Count,Percentage,Explanation" in summary_lines[0]
            assert "Total,3,100.0%,Total records analyzed" in summary_lines[-1]

            with open(ic_file, "r") as f:
                ic_lines = f.readlines()
            assert len(ic_lines) == 2, "In Copyright file should have header + 1 record"
            assert "In Copyright Book" in ic_lines[1]

            with open(research_file, "r") as f:
                research_lines = f.readlines()
            assert len(research_lines) == 2, "Research file should have header + 1 record"
            assert "Research Book" in research_lines[1]

            # Clean up CSV directory and files
            if csv_dir.exists():
                rmtree(csv_dir)

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
        # Determine copyright status
        pub.determine_copyright_status()

        with NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            temp_file = f.name

        try:
            export_to_csv([pub], temp_file, single_file=True)

            with open(temp_file, "r") as f:
                headers = f.readline().strip().split(",")

            # Check that expected simplified headers exist
            expected_headers = [
                "ID",
                "Title",
                "Author",
                "Year",
                "Publisher",
                "Country",
                "Status",
                "Match Summary",
                "Warning",
                "Registration Source ID",
                "Renewal Entry ID",
            ]

            for header in expected_headers:
                assert header in headers, f"Missing header: {header}"

            # Check basic ordering - MARC fields come before match fields
            marc_fields = ["ID", "Title", "Author", "Year", "Publisher"]
            match_fields = ["Registration Source ID", "Renewal Entry ID"]

            marc_indices = [headers.index(field) for field in marc_fields]
            match_indices = [headers.index(field) for field in match_fields]

            assert max(marc_indices) < min(
                match_indices
            ), "MARC fields should come before match fields"

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
        pub1.copyright_status = CopyrightStatus.US_REGISTERED_NOT_RENEWED.value

        pub2 = Publication(
            title="Book 2",
            author="Author 2",
            pub_date="1960",
            source_id="test_002",
            country_classification=CountryClassification.US,
        )
        pub2.copyright_status = CopyrightStatus.US_RENEWED.value

        publications = [pub1, pub2]

        with NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            temp_file = f.name

        try:
            # Use legacy behavior (single file)
            export_to_csv(publications, temp_file, single_file=True)

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

    def test_csv_non_us_consolidation(self) -> None:
        """Test that non-US records are consolidated into single file with country codes"""
        # Create test publications with foreign statuses
        pub1 = Publication(
            title="French Book",
            author="French Author",
            pub_date="1950",
            source_id="test_001",
            country_classification=CountryClassification.NON_US,
        )
        pub1.copyright_status = "FOREIGN_RENEWED_FRA"

        pub2 = Publication(
            title="German Book",
            author="German Author",
            pub_date="1960",
            source_id="test_002",
            country_classification=CountryClassification.NON_US,
        )
        pub2.copyright_status = "FOREIGN_NO_MATCH_DEU"

        pub3 = Publication(
            title="UK Book",
            author="UK Author",
            pub_date="1955",
            source_id="test_003",
            country_classification=CountryClassification.NON_US,
        )
        pub3.copyright_status = "FOREIGN_PRE_1929_GBR"

        publications = [pub1, pub2, pub3]

        with NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            temp_file = f.name

        try:
            # Use folder structure
            export_to_csv(publications, temp_file, single_file=False)

            # Check folder structure
            base_name = Path(temp_file).stem
            parent_dir = Path(temp_file).parent
            csv_dir = parent_dir / f"{base_name}_csv"

            # Check for foreign status files grouped by status type (all countries together)
            foreign_renewed_file = csv_dir / "foreign_renewed.csv"
            foreign_no_match_file = csv_dir / "foreign_no_match.csv"
            foreign_pre_file = csv_dir / "foreign_pre_1929.csv"

            assert (
                foreign_renewed_file.exists()
            ), f"Foreign renewed file should exist: {foreign_renewed_file}"
            assert (
                foreign_no_match_file.exists()
            ), f"Foreign no match file should exist: {foreign_no_match_file}"
            assert (
                foreign_pre_file.exists()
            ), f"Foreign pre-1929 file should exist: {foreign_pre_file}"

            # Check foreign renewed file (should have French record)
            with open(foreign_renewed_file, "r") as f:
                lines = f.readlines()
            assert len(lines) == 2, "Foreign renewed file should have header + 1 record"
            assert "Country_Code" in lines[0], "Header should include Country_Code column"
            assert "French Book" in lines[1], "Should contain French book"
            assert "FRA" in lines[1], "Should contain French country code"

            # Check foreign no match file (should have German record)
            with open(foreign_no_match_file, "r") as f:
                lines = f.readlines()
            assert len(lines) == 2, "Foreign no match file should have header + 1 record"
            assert "German Book" in lines[1], "Should contain German book"
            assert "DEU" in lines[1], "Should contain German country code"

            # Check foreign pre-1929 file (should have UK record)
            with open(foreign_pre_file, "r") as f:
                lines = f.readlines()
            assert len(lines) == 2, "Foreign pre-1929 file should have header + 1 record"
            assert "UK Book" in lines[1], "Should contain UK book"
            assert "GBR" in lines[1], "Should contain British country code"

            # Check summary file includes explanations
            summary_file = csv_dir / "_summary.csv"
            with open(summary_file, "r") as f:
                summary_content = f.read()

            assert "Foreign work" in summary_content, "Summary should explain foreign statuses"

            # Clean up
            if csv_dir.exists():
                rmtree(csv_dir)

        finally:
            try:
                unlink(temp_file)
            except FileNotFoundError:
                pass
