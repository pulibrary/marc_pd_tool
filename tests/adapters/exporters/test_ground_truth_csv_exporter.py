# tests/adapters/exporters/test_ground_truth_csv_exporter.py

"""Tests for ground truth CSV export functionality"""

# Standard library imports
import csv
from os.path import exists
from os.path import join
from tempfile import TemporaryDirectory

# Third party imports
from pytest import fixture

# Local imports
from marc_pd_tool.adapters.api import MarcCopyrightAnalyzer
from marc_pd_tool.adapters.exporters.ground_truth_csv_exporter import (
    export_ground_truth_csv,
)
from marc_pd_tool.core.domain.enums import CopyrightStatus
from marc_pd_tool.core.domain.enums import CountryClassification
from marc_pd_tool.core.domain.enums import MatchType
from marc_pd_tool.core.domain.match_result import MatchResult
from marc_pd_tool.core.domain.publication import Publication


class TestGroundTruthCSVExport:
    """Test ground truth CSV export"""

    @fixture
    def analyzer(self):
        """Create an analyzer instance"""
        return MarcCopyrightAnalyzer()

    @fixture
    def sample_ground_truth_publications(self):
        """Create sample ground truth publications with matches for testing"""
        # Create MARC record with registration match
        marc_record = Publication(
            title="The Great Gatsby",
            author="F. Scott Fitzgerald",
            main_author="Fitzgerald, F. Scott (Francis Scott), 1896-1940",
            publisher="Charles Scribner's Sons",
            pub_date="1925",
            lccn="25011316",
        )
        marc_record.source_id = "marc_001"
        marc_record.country_code = "xxu"
        marc_record.country_classification = CountryClassification.US
        marc_record.language_code = "eng"
        marc_record.year = 1925
        marc_record.normalized_lccn = "25011316"

        # Add registration match
        marc_record.registration_match = MatchResult(
            matched_title="The great Gatsby",
            matched_author="F. Scott Fitzgerald",
            matched_publisher="Scribner",
            similarity_score=95.0,
            title_score=98.0,
            author_score=100.0,
            publisher_score=87.0,
            year_difference=0,
            source_id="REG12345",
            source_type="registration",
            matched_date="1925-04-10",
            match_type=MatchType.LCCN,
            normalized_title="the great gatsby",
            normalized_author="f scott fitzgerald",
        )

        # Set copyright status
        marc_record.copyright_status = CopyrightStatus.US_RENEWED.value

        return [marc_record]

    def test_export_ground_truth_csv_basic(self, sample_ground_truth_publications):
        """Test basic CSV export functionality"""
        with TemporaryDirectory() as temp_dir:
            output_path = join(temp_dir, "ground_truth.csv")

            # Export to CSV
            export_ground_truth_csv(sample_ground_truth_publications, output_path)

            # Verify file exists
            assert exists(output_path)

            # Read and verify content
            with open(output_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)

                assert len(rows) == 1
                row = rows[0]

                # Check MARC data
                assert row["marc_title_original"] == "The Great Gatsby"
                assert row["marc_author_original"] == "F. Scott Fitzgerald"
                assert row["marc_publisher_original"] == "Charles Scribner's Sons"
                assert row["marc_year"] == "1925"
                assert row["marc_lccn"] == "25011316"
                assert row["marc_country_code"] == "xxu"
                assert row["marc_language_code"] == "eng"

                # Check match data
                assert row["match_type"] == "registration"
                assert row["match_title"] == "The great Gatsby"
                assert row["match_author"] == "F. Scott Fitzgerald"
                assert row["match_publisher"] == "Scribner"
                assert row["match_source_id"] == "REG12345"

                # Check scores
                assert float(row["title_score"]) == 98.0
                assert float(row["author_score"]) == 100.0
                assert float(row["publisher_score"]) == 87.0
                assert float(row["combined_score"]) == 95.0

    def test_export_ground_truth_csv_normalized_fields(self, sample_ground_truth_publications):
        """Test that normalized and stemmed fields are exported correctly"""
        with TemporaryDirectory() as temp_dir:
            output_path = join(temp_dir, "ground_truth.csv")

            export_ground_truth_csv(sample_ground_truth_publications, output_path)

            with open(output_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                row = next(reader)

                # Check normalized fields exist
                assert "marc_title_normalized" in row
                assert "marc_author_normalized" in row
                assert "marc_publisher_normalized" in row

                # Check stemmed fields exist
                assert "marc_title_stemmed" in row
                assert "marc_author_stemmed" in row
                assert "marc_publisher_stemmed" in row

                # Check match normalized fields
                assert "match_title_normalized" in row
                assert "match_author_normalized" in row
                assert "match_publisher_normalized" in row

    def test_export_ground_truth_csv_headers(self):
        """Test that all expected headers are present in the CSV"""
        with TemporaryDirectory() as temp_dir:
            output_path = join(temp_dir, "ground_truth.csv")

            # Export empty list to check headers
            export_ground_truth_csv([], output_path)

            with open(output_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                headers = reader.fieldnames

                # Check MARC headers
                assert "marc_id" in headers
                assert "marc_title_original" in headers
                assert "marc_author_original" in headers
                assert "marc_main_author_original" in headers
                assert "marc_publisher_original" in headers
                assert "marc_year" in headers
                assert "marc_lccn" in headers
                assert "marc_country_code" in headers
                assert "marc_language_code" in headers

                # Check match headers
                assert "match_type" in headers
                assert "match_title" in headers
                assert "match_author" in headers
                assert "match_publisher" in headers
                assert "match_source_id" in headers

                # Check score headers
                assert "title_score" in headers
                assert "author_score" in headers
                assert "publisher_score" in headers
                assert "combined_score" in headers
                assert "year_difference" in headers
                assert "copyright_status" in headers

    def test_export_ground_truth_csv_with_renewal(self):
        """Test exporting a publication with renewal match"""
        # Create MARC record with renewal match
        marc_record = Publication(title="Test Book", author="Test Author", lccn="12345678")
        marc_record.year = 1950
        marc_record.normalized_lccn = "12345678"

        # Add renewal match
        marc_record.renewal_match = MatchResult(
            matched_title="Test Book",
            matched_author="Test Author",
            similarity_score=90.0,
            title_score=95.0,
            author_score=85.0,
            year_difference=0,
            source_id="REN67890",
            source_type="renewal",
            match_type=MatchType.LCCN,
        )

        with TemporaryDirectory() as temp_dir:
            output_path = join(temp_dir, "ground_truth.csv")

            export_ground_truth_csv([marc_record], output_path)

            with open(output_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                row = next(reader)

                assert row["match_type"] == "renewal"
                assert row["match_source_id"] == "REN67890"

    def test_export_ground_truth_csv_handles_missing_data(self):
        """Test that export handles publications with missing fields gracefully"""
        # Create minimal MARC record
        marc_record = Publication(title="Minimal Book")
        marc_record.normalized_lccn = "99999999"

        # Add minimal match
        marc_record.registration_match = MatchResult(
            matched_title="Minimal Book",
            matched_author="",
            similarity_score=50.0,
            title_score=50.0,
            author_score=0.0,
            year_difference=0,
            source_id="REG99999",
            source_type="registration",
            match_type=MatchType.LCCN,
        )

        with TemporaryDirectory() as temp_dir:
            output_path = join(temp_dir, "ground_truth.csv")

            export_ground_truth_csv([marc_record], output_path)

            with open(output_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                row = next(reader)

                # Check that missing fields are empty strings
                assert row["marc_author_original"] == ""
                assert row["marc_publisher_original"] == ""
                assert row["marc_year"] == ""
                assert row["match_author"] == ""
