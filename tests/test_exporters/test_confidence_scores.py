# tests/test_exporters/test_confidence_scores.py

"""Tests for confidence score tracking in match results and CSV output"""

# Standard library imports
from csv import reader
from os import unlink
from tempfile import NamedTemporaryFile

# Local imports
from marc_pd_tool.data.publication import CountryClassification
from marc_pd_tool.data.publication import MatchResult
from marc_pd_tool.data.publication import Publication
from marc_pd_tool.exporters.csv_exporter import CSVExporter
from marc_pd_tool.exporters.json_exporter import save_matches_json

# pytest imported automatically by test runner


def export_to_csv(publications, csv_file, single_file=True):
    """Helper to export publications to CSV via JSON"""
    # Standard library imports
    import os
    import tempfile

    temp_fd, temp_json = tempfile.mkstemp(suffix=".json")
    os.close(temp_fd)

    try:
        save_matches_json(publications, temp_json, single_file=single_file)
        exporter = CSVExporter(temp_json, csv_file, single_file=single_file)
        exporter.export()
    finally:
        if os.path.exists(temp_json):
            os.unlink(temp_json)


class TestConfidenceScores:
    """Test confidence score tracking and CSV output"""

    def test_match_result_includes_individual_scores(self):
        """Test that MatchResult captures title and author confidence scores"""
        match = MatchResult(
            matched_title="Test Book (matched)",
            matched_author="Test Author (matched)",
            similarity_score=85.5,
            title_score=90.0,
            author_score=75.0,
            year_difference=1,
            source_id="reg_001",
            source_type="registration",
            matched_date="1950",
        )

        assert match.title_score == 90.0
        assert match.author_score == 75.0
        assert match.similarity_score == 85.5
        assert match.source_id == "reg_001"

    def test_publication_to_dict_includes_scores(self):
        """Test that Publication.to_dict() includes individual confidence scores"""
        pub = Publication(
            title="Test Book",
            author="Test Author",
            pub_date="1950",
            source_id="test_001",
            country_classification=CountryClassification.US,
        )

        # Add a match with confidence scores
        match = MatchResult(
            matched_title="Test Book (matched)",
            matched_author="Test Author (matched)",
            similarity_score=85.5,
            title_score=90.0,
            author_score=75.0,
            year_difference=1,
            source_id="reg_001",
            source_type="registration",
            matched_date="1950",
        )
        pub.set_registration_match(match)

        pub_dict = pub.to_dict()

        # Check that match details include individual scores
        assert pub_dict["registration_match"] is not None
        reg_match = pub_dict["registration_match"]
        assert reg_match["title_score"] == 90.0
        assert reg_match["author_score"] == 75.0
        assert reg_match["similarity_score"] == 85.5

    def test_csv_output_includes_confidence_score_headers(self):
        """Test that CSV output includes proper headers for confidence scores"""
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
            export_to_csv([pub], temp_file, single_file=True)

            with open(temp_file, "r") as f:
                headers = f.readline().strip().split(",")

            # Check for simplified headers
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

            # Ensure old headers are not present
            assert (
                "Renewal Source ID" not in headers
            ), "Old 'Renewal Source ID' header should not be present"
            assert "Renewal ID" not in headers, "Old 'Renewal ID' header should not be present"
            assert (
                "Original Registration ID" not in headers
            ), "Old 'Original Registration ID' header should not be present"

        finally:
            unlink(temp_file)

    def test_csv_output_with_renewal_entry_id(self):
        """Test that CSV output correctly shows renewal entry ID"""
        pub = Publication(
            title="Test Book",
            author="Test Author",
            pub_date="1950",
            source_id="test_001",
            country_classification=CountryClassification.US,
        )

        # Add renewal match with entry ID (UUID format)
        ren_match = MatchResult(
            matched_title="Test Book (ren)",
            matched_author="Test Author (ren)",
            similarity_score=88.2,
            title_score=92.0,
            author_score=80.0,
            year_difference=0,
            source_id="b3ce7263-9e8b-5f9e-b1a0-190723af8d29",
            source_type="renewal",
            matched_date="1950-01-01",
        )
        pub.set_renewal_match(ren_match)

        # Determine copyright status
        pub.determine_copyright_status()

        with NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            temp_file = f.name

        try:
            export_to_csv([pub], temp_file, single_file=True)

            with open(temp_file, "r") as f:
                csv_reader = reader(f)
                headers = next(csv_reader)
                data_row = next(csv_reader)

            # Create a mapping for easier access
            row_dict = dict(zip(headers, data_row))

            # Check that renewal entry ID field is correct
            assert row_dict["Renewal Entry ID"] == "b3ce7263-9e8b-5f9e-b1a0-190723af8d29"

        finally:
            unlink(temp_file)

    def test_csv_output_includes_confidence_scores_data(self):
        """Test that CSV output includes actual confidence score data"""
        pub = Publication(
            title="Test Book",
            author="Test Author",
            pub_date="1950",
            source_id="test_001",
            country_classification=CountryClassification.US,
        )

        # Add registration match
        reg_match = MatchResult(
            matched_title="Test Book (reg)",
            matched_author="Test Author (reg)",
            similarity_score=85.5,
            title_score=90.0,
            author_score=75.0,
            year_difference=1,
            source_id="reg_001",
            source_type="registration",
            matched_date="1950",
        )
        pub.set_registration_match(reg_match)

        # Add renewal match
        ren_match = MatchResult(
            matched_title="Test Book (ren)",
            matched_author="Test Author (ren)",
            similarity_score=88.2,
            title_score=92.0,
            author_score=80.0,
            year_difference=0,
            source_id="ren_001",
            source_type="renewal",
            matched_date="1950-01-01",
        )
        pub.set_renewal_match(ren_match)

        # Determine copyright status
        pub.determine_copyright_status()

        with NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            temp_file = f.name

        try:
            export_to_csv([pub], temp_file, single_file=True)

            with open(temp_file, "r") as f:
                csv_reader = reader(f)
                headers = next(csv_reader)
                data_row = next(csv_reader)

            # Create a mapping for easier access
            row_dict = dict(zip(headers, data_row))

            # Check that the simplified CSV format contains expected data
            assert row_dict["ID"] == "test_001"
            assert row_dict["Title"] == "Test Book"
            assert row_dict["Author"] == "Test Author"
            assert row_dict["Year"] == "1950"
            assert row_dict["Status"] == "IN_COPYRIGHT"  # Has renewal match, so still in copyright

            # Check match summary format (should show percentages for non-LCCN matches)
            assert "Reg: 86%" in row_dict["Match Summary"]  # 85.5 rounds to 86
            assert "Ren: 88%" in row_dict["Match Summary"]  # 88.2 rounds to 88

            # Check source IDs
            assert row_dict["Registration Source ID"] == "reg_001"
            assert row_dict["Renewal Entry ID"] == "ren_001"

        finally:
            unlink(temp_file)

    def test_csv_output_empty_scores_for_no_matches(self):
        """Test that CSV output shows empty strings for publications with no matches"""
        pub = Publication(
            title="Test Book",
            author="Test Author",
            pub_date="1950",
            source_id="test_001",
            country_classification=CountryClassification.US,
        )

        # No matches added
        # Determine copyright status
        pub.determine_copyright_status()

        with NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            temp_file = f.name

        try:
            export_to_csv([pub], temp_file, single_file=True)

            with open(temp_file, "r") as f:
                csv_reader = reader(f)
                headers = next(csv_reader)
                data_row = next(csv_reader)

            # Create a mapping for easier access
            row_dict = dict(zip(headers, data_row))

            # Check the simplified format for no matches
            assert row_dict["Match Summary"] == "Reg: None, Ren: None"
            assert row_dict["Registration Source ID"] == ""
            assert row_dict["Renewal Entry ID"] == ""

        finally:
            unlink(temp_file)

    def test_csv_output_single_match_behavior(self):
        """Test that CSV output correctly shows single match data"""
        pub = Publication(
            title="Test Book",
            author="Test Author",
            pub_date="1950",
            source_id="test_001",
            country_classification=CountryClassification.US,
        )

        # Add single registration match
        match = MatchResult(
            matched_title="Test Book",
            matched_author="Test Author",
            similarity_score=90.0,
            title_score=95.0,
            author_score=80.0,
            year_difference=0,
            source_id="reg_002",
            source_type="registration",
            matched_date="1955",
        )
        pub.set_registration_match(match)

        # Determine copyright status
        pub.determine_copyright_status()

        with NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            temp_file = f.name

        try:
            export_to_csv([pub], temp_file, single_file=True)

            with open(temp_file, "r") as f:
                csv_reader = reader(f)
                headers = next(csv_reader)
                data_row = next(csv_reader)

            # Create a mapping for easier access
            row_dict = dict(zip(headers, data_row))

            # Check simplified format for single match
            assert "Reg: 90%" in row_dict["Match Summary"]
            assert "Ren: None" in row_dict["Match Summary"]
            assert row_dict["Registration Source ID"] == "reg_002"
            assert row_dict["Renewal Entry ID"] == ""

        finally:
            unlink(temp_file)
