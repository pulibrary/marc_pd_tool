"""Tests for confidence score tracking in match results and CSV output"""

# Standard library imports
from csv import reader
from os import unlink
from tempfile import NamedTemporaryFile

# Local imports
from marc_pd_tool.batch_processor import save_matches_csv
from marc_pd_tool.enums import AuthorType
from marc_pd_tool.enums import CopyrightStatus
from marc_pd_tool.enums import CountryClassification
from marc_pd_tool.publication import MatchResult
from marc_pd_tool.publication import Publication

# pytest imported automatically by test runner


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
            author_type=AuthorType.PERSONAL,
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
            author_type=AuthorType.PERSONAL,
        )

        with NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            temp_file = f.name

        try:
            save_matches_csv([pub], temp_file)

            with open(temp_file, "r") as f:
                headers = f.readline().strip().split(",")

            # Check for confidence score headers
            expected_headers = [
                "Registration Similarity Score",
                "Renewal Similarity Score",
                "Registration Title Score",
                "Registration Author Score",
                "Registration Combined Score",
                "Renewal Title Score",
                "Renewal Author Score",
                "Renewal Combined Score",
            ]

            # Check for renewal entry ID header
            assert "Renewal Entry ID" in headers, "Missing 'Renewal Entry ID' header"

            for header in expected_headers:
                assert header in headers, f"Missing header: {header}"
                
            # Ensure old headers are not present
            assert "Renewal Source ID" not in headers, "Old 'Renewal Source ID' header should not be present"
            assert "Renewal ID" not in headers, "Old 'Renewal ID' header should not be present"
            assert "Original Registration ID" not in headers, "Old 'Original Registration ID' header should not be present"

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
            author_type=AuthorType.PERSONAL,
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
        )
        pub.set_renewal_match(ren_match)

        with NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            temp_file = f.name

        try:
            save_matches_csv([pub], temp_file)

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
            author_type=AuthorType.PERSONAL,
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
        )
        pub.set_renewal_match(ren_match)

        with NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            temp_file = f.name

        try:
            save_matches_csv([pub], temp_file)

            with open(temp_file, "r") as f:
                csv_reader = reader(f)
                headers = next(csv_reader)
                data_row = next(csv_reader)

            # Create a mapping for easier access
            row_dict = dict(zip(headers, data_row))

            # Check simple similarity scores
            assert row_dict["Registration Similarity Score"] == "85.5"
            assert row_dict["Renewal Similarity Score"] == "88.2"

            # Check registration scores
            assert row_dict["Registration Title Score"] == "90.0"
            assert row_dict["Registration Author Score"] == "75.0"
            assert row_dict["Registration Combined Score"] == "85.5"

            # Check renewal scores
            assert row_dict["Renewal Title Score"] == "92.0"
            assert row_dict["Renewal Author Score"] == "80.0"
            assert row_dict["Renewal Combined Score"] == "88.2"

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
            author_type=AuthorType.PERSONAL,
        )

        # No matches added

        with NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            temp_file = f.name

        try:
            save_matches_csv([pub], temp_file)

            with open(temp_file, "r") as f:
                csv_reader = reader(f)
                headers = next(csv_reader)
                data_row = next(csv_reader)

            # Create a mapping for easier access
            row_dict = dict(zip(headers, data_row))

            # Check that score fields are empty
            assert row_dict["Registration Similarity Score"] == ""
            assert row_dict["Renewal Similarity Score"] == ""
            assert row_dict["Registration Title Score"] == ""
            assert row_dict["Registration Author Score"] == ""
            assert row_dict["Registration Combined Score"] == ""
            assert row_dict["Renewal Title Score"] == ""
            assert row_dict["Renewal Author Score"] == ""
            assert row_dict["Renewal Combined Score"] == ""

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
            author_type=AuthorType.PERSONAL,
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
        )
        pub.set_registration_match(match)

        with NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            temp_file = f.name

        try:
            save_matches_csv([pub], temp_file)

            with open(temp_file, "r") as f:
                csv_reader = reader(f)
                headers = next(csv_reader)
                data_row = next(csv_reader)

            # Create a mapping for easier access
            row_dict = dict(zip(headers, data_row))

            # Should show scores from the single match
            assert row_dict["Registration Similarity Score"] == "90.0"
            assert row_dict["Registration Title Score"] == "95.0"
            assert row_dict["Registration Author Score"] == "80.0"
            assert row_dict["Registration Combined Score"] == "90.0"

        finally:
            unlink(temp_file)
