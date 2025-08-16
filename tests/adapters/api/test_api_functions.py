# tests/adapters/api/test_api_functions.py

"""Tests for API helper functions and utilities"""

# Standard library imports
from pathlib import Path
from tempfile import TemporaryDirectory

# Local imports
from marc_pd_tool.adapters.exporters.json_exporter import save_matches_json
from marc_pd_tool.core.domain.enums import CopyrightStatus
from tests.fixtures.publications import PublicationBuilder


class TestSaveMatchesJson:
    """Test the save_matches_json function"""

    def test_save_matches_json_basic(self):
        """Test basic JSON export functionality"""
        # Create test publications
        pubs = [
            PublicationBuilder.basic_us_publication(source_id="test1"),
            PublicationBuilder.basic_us_publication(source_id="test2"),
        ]
        pubs[0].copyright_status = CopyrightStatus.US_REGISTERED_NOT_RENEWED.value
        pubs[1].copyright_status = CopyrightStatus.US_RENEWED.value

        with TemporaryDirectory() as temp_dir:
            output_file = str(Path(temp_dir) / "results.json")

            # Save to JSON
            save_matches_json(pubs, output_file)

            # Verify file was created
            assert Path(output_file).exists()

            # Load and verify content
            # Standard library imports
            import json

            with open(output_file) as f:
                data = json.load(f)

            assert data["metadata"]["total_records"] == 2
            assert len(data["records"]) == 2
            assert data["records"][0]["marc"]["id"] == "test1"
            assert data["records"][0]["analysis"]["status"] == "US_REGISTERED_NOT_RENEWED"
            assert data["records"][1]["marc"]["id"] == "test2"
            assert data["records"][1]["analysis"]["status"] == "US_RENEWED"

    def test_save_matches_json_with_parameters(self):
        """Test JSON export with processing parameters"""
        pubs = [PublicationBuilder.basic_us_publication()]

        parameters = {
            "title_threshold": 45,
            "author_threshold": 35,
            "year_tolerance": 2,
            "us_only": True,
        }

        with TemporaryDirectory() as temp_dir:
            output_file = str(Path(temp_dir) / "results.json")

            # Save with parameters
            save_matches_json(pubs, output_file, parameters=parameters)

            # Load and verify parameters are included
            # Standard library imports
            import json

            with open(output_file) as f:
                data = json.load(f)

            assert "parameters" in data["metadata"]
            assert data["metadata"]["parameters"]["title_threshold"] == 45
            assert data["metadata"]["parameters"]["author_threshold"] == 35
            assert data["metadata"]["parameters"]["year_tolerance"] == 2
            assert data["metadata"]["parameters"]["us_only"] is True

    def test_save_matches_json_compressed(self):
        """Test JSON export with compression"""
        pubs = [PublicationBuilder.basic_us_publication() for _ in range(10)]

        with TemporaryDirectory() as temp_dir:
            output_file = str(Path(temp_dir) / "results.json")

            # Save with compression
            save_matches_json(pubs, output_file, compress=True)

            # File should have .gz extension
            compressed_file = Path(output_file + ".gz")
            assert compressed_file.exists()
            assert not Path(output_file).exists()

            # Verify we can read the compressed file
            # Standard library imports
            import gzip
            import json

            with gzip.open(compressed_file, "rt") as f:
                data = json.load(f)

            assert data["metadata"]["total_records"] == 10
            assert len(data["records"]) == 10

    def test_save_matches_json_not_pretty(self):
        """Test JSON export without pretty printing"""
        pubs = [PublicationBuilder.basic_us_publication()]

        with TemporaryDirectory() as temp_dir:
            output_file = str(Path(temp_dir) / "results.json")

            # Save without pretty printing
            save_matches_json(pubs, output_file, pretty=False)

            # Read file and check it's minified
            content = Path(output_file).read_text()
            # Minified JSON should be a single line (plus final newline)
            lines = content.strip().split("\n")
            assert len(lines) == 1

    def test_save_matches_json_empty_list(self):
        """Test JSON export with empty publication list"""
        with TemporaryDirectory() as temp_dir:
            output_file = str(Path(temp_dir) / "empty.json")

            # Save empty list
            save_matches_json([], output_file)

            # Verify file structure
            # Standard library imports
            import json

            with open(output_file) as f:
                data = json.load(f)

            assert data["metadata"]["total_records"] == 0
            assert data["records"] == []
            assert "processing_date" in data["metadata"]

    def test_save_matches_json_unicode_handling(self):
        """Test JSON export handles unicode correctly"""
        pub = PublicationBuilder.basic_us_publication()
        pub.original_title = "Café société"
        pub.original_author = "José Müller"

        with TemporaryDirectory() as temp_dir:
            output_file = str(Path(temp_dir) / "unicode.json")

            save_matches_json([pub], output_file)

            # Verify unicode is preserved
            # Standard library imports
            import json

            with open(output_file, encoding="utf-8") as f:
                data = json.load(f)

            assert data["records"][0]["marc"]["original"]["title"] == "Café société"
            assert data["records"][0]["marc"]["original"]["author_245c"] == "José Müller"
