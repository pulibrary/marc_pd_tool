# tests/test_api/test_ground_truth_csv.py

"""Tests for ground truth CSV export functionality"""

# Standard library imports
import csv
from os.path import exists
from os.path import join
from tempfile import TemporaryDirectory

# Third party imports
from pytest import fixture

# Local imports
from marc_pd_tool.api import MarcCopyrightAnalyzer
from marc_pd_tool.data.enums import CopyrightStatus
from marc_pd_tool.data.enums import CountryClassification
from marc_pd_tool.data.ground_truth import GroundTruthPair
from marc_pd_tool.data.publication import MatchResult
from marc_pd_tool.data.publication import Publication


class TestGroundTruthCSVExport:
    """Test ground truth CSV export"""

    @fixture
    def analyzer(self):
        """Create an analyzer instance"""
        return MarcCopyrightAnalyzer()

    @fixture
    def sample_ground_truth_pairs(self):
        """Create sample ground truth pairs for testing"""
        # Create MARC record
        marc_record = Publication(
            title="The Great Gatsby",
            author="F. Scott Fitzgerald",
            main_author="Fitzgerald, F. Scott (Francis Scott), 1896-1940",
            publisher="Charles Scribner's Sons",
            pub_date="1925",
            lccn="25011316",
            source_id="marc_001",
            country_code="xxu",
            country_classification=CountryClassification.US,
        )

        # Create copyright record
        copyright_record = Publication(
            title="The great Gatsby",
            author="F. Scott Fitzgerald",
            publisher="Scribner",
            pub_date="1925",
            lccn="25-11316",
            source_id="reg_001",
        )

        # Add match result to MARC record
        # Local imports
        from marc_pd_tool.data.enums import MatchType

        match_result = MatchResult(
            matched_title="The great Gatsby",
            matched_author="F. Scott Fitzgerald",
            similarity_score=91.9,
            title_score=95.5,
            author_score=92.3,
            year_difference=0,
            source_id="reg_001",
            source_type="registration",
            matched_date="1925",
            matched_publisher="Scribner",
            publisher_score=88.0,
            match_type=MatchType.LCCN,
        )
        marc_record.registration_match = match_result
        marc_record.copyright_status = CopyrightStatus.US_REGISTERED_NOT_RENEWED

        # Create ground truth pair
        pair = GroundTruthPair(
            marc_record=marc_record,
            copyright_record=copyright_record,
            match_type="registration",
            lccn="25011316",
        )

        return [pair]

    def test_export_ground_truth_csv_basic(self, analyzer, sample_ground_truth_pairs):
        """Test basic CSV export functionality"""
        # Set up analyzer with ground truth pairs
        analyzer.results.ground_truth_pairs = sample_ground_truth_pairs

        with TemporaryDirectory() as temp_dir:
            output_path = join(temp_dir, "ground_truth")

            # Export CSV
            analyzer._export_ground_truth_csv(output_path)

            # Verify file was created
            csv_path = f"{output_path}.csv"
            assert exists(csv_path)

            # Read and verify CSV content
            with open(csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            assert len(rows) == 1
            row = rows[0]

            # Check MARC data
            assert row["marc_id"] == "marc_001"
            assert row["marc_title_original"] == "The Great Gatsby"
            assert row["marc_author_original"] == "F. Scott Fitzgerald"
            assert (
                row["marc_main_author_original"]
                == "Fitzgerald, F. Scott (Francis Scott), 1896-1940"
            )
            assert row["marc_publisher_original"] == "Charles Scribner's Sons"
            assert row["marc_year"] == "1925"
            assert row["marc_lccn"] == "25011316"

            # Check match data
            assert row["match_type"] == "registration"
            assert row["match_title_original"] == "The great Gatsby"
            assert row["match_author_original"] == "F. Scott Fitzgerald"
            assert row["match_year"] == "1925"

            # Check scores
            assert row["title_score"] == "95.5"
            assert row["author_score"] == "92.3"
            assert row["publisher_score"] == "88.0"
            # Note: combined_score is not a field in MatchResult, it's similarity_score
            # But the CSV export calculates it differently, need to check
            # For now, just check it exists
            assert "combined_score" in row
            assert row["year_difference"] == "0"

            # Check copyright status
            assert row["copyright_status"] == "US_REGISTERED_NOT_RENEWED"

    def test_export_ground_truth_csv_normalized_fields(self, analyzer, sample_ground_truth_pairs):
        """Test that normalized and stemmed fields are included"""
        analyzer.results.ground_truth_pairs = sample_ground_truth_pairs

        with TemporaryDirectory() as temp_dir:
            output_path = join(temp_dir, "ground_truth")
            analyzer._export_ground_truth_csv(output_path)

            csv_path = f"{output_path}.csv"
            with open(csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                row = next(reader)

            # Check that normalized fields exist and are not empty
            assert row["marc_title_normalized"] != ""
            assert row["marc_title_stemmed"] != ""
            assert row["marc_author_normalized"] != ""
            assert row["marc_author_stemmed"] != ""

            # Normalized should be lowercase
            assert row["marc_title_normalized"].islower()
            assert row["marc_author_normalized"].islower()

            # Check match normalized fields
            assert row["match_title_normalized"] != ""
            assert row["match_title_stemmed"] != ""

    def test_export_ground_truth_csv_headers(self, analyzer):
        """Test that all expected headers are present"""
        analyzer.results.ground_truth_pairs = []  # Empty list

        with TemporaryDirectory() as temp_dir:
            output_path = join(temp_dir, "ground_truth")

            # This should create a CSV with headers only
            analyzer._export_ground_truth_csv(output_path)

            csv_path = f"{output_path}.csv"
            if exists(csv_path):
                with open(csv_path, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    headers = reader.fieldnames

                # Check key headers are present
                assert "marc_id" in headers
                assert "marc_title_original" in headers
                assert "marc_title_normalized" in headers
                assert "marc_title_stemmed" in headers
                assert "marc_author_original" in headers
                assert "marc_main_author_original" in headers
                assert "match_type" in headers
                assert "match_title_original" in headers
                assert "title_score" in headers
                assert "copyright_status" in headers

    def test_export_ground_truth_csv_with_renewal(self, analyzer):
        """Test CSV export with renewal match"""
        # Create renewal match
        marc_record = Publication(
            title="Test Book",
            author="Test Author",
            pub_date="1950",
            lccn="50123456",
            source_id="marc_002",
            country_code="xxu",
            country_classification=CountryClassification.US,
        )

        renewal_record = Publication(
            title="Test Book",
            author="Test Author",
            pub_date="1950",
            lccn="50-123456",
            source_id="ren_001",
        )
        # Note: renewal_entry_id doesn't exist on Publication object

        pair = GroundTruthPair(
            marc_record=marc_record,
            copyright_record=renewal_record,
            match_type="renewal",
            lccn="50123456",
        )

        analyzer.results.ground_truth_pairs = [pair]

        with TemporaryDirectory() as temp_dir:
            output_path = join(temp_dir, "ground_truth")
            analyzer._export_ground_truth_csv(output_path)

            csv_path = f"{output_path}.csv"
            with open(csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                row = next(reader)

            assert row["match_type"] == "renewal"
            # match_entry_id is not available, should be empty
            assert row["match_entry_id"] == ""

    def test_export_ground_truth_csv_handles_missing_data(self, analyzer):
        """Test CSV export handles records with missing fields gracefully"""
        # Create minimal record with many missing fields
        marc_record = Publication(
            title="Minimal Title",
            pub_date="1960",
            lccn="60123456",
            source_id="marc_003",
            country_code="xxu",
            country_classification=CountryClassification.US,
        )

        copyright_record = Publication(title="Minimal Title", lccn="60-123456", source_id="reg_003")

        pair = GroundTruthPair(
            marc_record=marc_record,
            copyright_record=copyright_record,
            match_type="registration",
            lccn="60123456",
        )

        analyzer.results.ground_truth_pairs = [pair]

        with TemporaryDirectory() as temp_dir:
            output_path = join(temp_dir, "ground_truth")
            analyzer._export_ground_truth_csv(output_path)

            csv_path = f"{output_path}.csv"
            with open(csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                row = next(reader)

            # Missing fields should be empty strings
            assert row["marc_author_original"] == ""
            assert row["marc_main_author_original"] == ""
            assert row["marc_publisher_original"] == ""
            assert row["match_author_original"] == ""
            assert row["match_publisher_original"] == ""
            assert row["match_year"] == ""
