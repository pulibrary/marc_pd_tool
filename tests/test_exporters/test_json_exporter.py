# tests/test_exporters/test_json_exporter.py

"""Tests for JSON export functionality"""

# Standard library imports
import json
from os import remove
from os.path import exists
from pathlib import Path
from tempfile import NamedTemporaryFile

# Local imports
from marc_pd_tool.exporters.json_exporter import save_matches_json


class TestJSONExporter:
    """Test JSON export functionality"""

    def test_json_export_single_file(self, sample_publications):
        """Test that JSON export creates a single comprehensive file"""
        with NamedTemporaryFile(suffix=".json", delete=False) as f:
            output_path = f.name

        try:
            save_matches_json(sample_publications, output_path)

            # Verify file was created
            assert exists(output_path)

            # Load and verify JSON structure
            with open(output_path, "r") as f:
                data = json.load(f)

            # Check metadata
            assert "metadata" in data
            assert data["metadata"]["total_records"] == 3
            assert "processing_date" in data["metadata"]
            assert "status_counts" in data["metadata"]

            # Check records
            assert "records" in data
            assert len(data["records"]) == 3

            # Check first publication structure
            pub1 = data["records"][0]
            assert pub1["marc"]["id"] == "123"
            assert pub1["marc"]["original"]["title"] == "Test Book One"
            assert pub1["analysis"]["status"] == "PD_US_NOT_RENEWED"
            assert "matches" in pub1
            assert pub1["matches"]["registration"]["found"] is True
            assert pub1["matches"]["registration"]["id"] == "REG123"

        finally:
            if exists(output_path):
                remove(output_path)

    def test_json_export_no_multiple_files(self, sample_publications):
        """Test that JSON export no longer creates multiple files"""
        with NamedTemporaryFile(suffix=".json", delete=False) as f:
            output_path = f.name

        try:
            # JSON export now always creates a single file
            save_matches_json(sample_publications, output_path)

            # Verify only the single file was created
            assert exists(output_path)

            # Check that separate files were NOT created
            path = Path(output_path)
            base = path.stem
            parent = path.parent

            pd_file = parent / f"{base}_pd_no_renewal.json"
            copyright_file = parent / f"{base}_in_copyright.json"
            research_file = parent / f"{base}_research_us_status.json"

            assert not exists(pd_file)
            assert not exists(copyright_file)
            assert not exists(research_file)

            # Verify all records are in the single file
            with open(output_path, "r") as f:
                data = json.load(f)
            assert data["metadata"]["total_records"] == 3
            assert len(data["records"]) == 3

        finally:
            if exists(output_path):
                remove(output_path)

    def test_json_export_no_pretty_print(self, sample_publications):
        """Test JSON export without pretty printing"""
        with NamedTemporaryFile(suffix=".json", delete=False) as f:
            output_path = f.name

        try:
            save_matches_json(sample_publications, output_path, pretty=False)

            # Verify file was created
            assert exists(output_path)

            # Check that it's not pretty printed (single line)
            with open(output_path, "r") as f:
                content = f.read()
            assert "\n" not in content.strip()  # No newlines except at end

            # Verify it's still valid JSON
            data = json.loads(content)
            assert data["metadata"]["total_records"] == 3

        finally:
            if exists(output_path):
                remove(output_path)

    def test_json_export_with_unicode(self, sample_publications):
        """Test JSON export handles unicode correctly"""
        # Modify a publication to have unicode
        sample_publications[0].original_title = "Test Book with Café"
        sample_publications[0].original_author = "Müller, José"

        with NamedTemporaryFile(suffix=".json", delete=False) as f:
            output_path = f.name

        try:
            save_matches_json(sample_publications, output_path)

            # Load and verify unicode is preserved
            with open(output_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            assert data["records"][0]["marc"]["original"]["title"] == "Test Book with Café"
            assert data["records"][0]["marc"]["original"]["author_245c"] == "Müller, José"

        finally:
            if exists(output_path):
                remove(output_path)
