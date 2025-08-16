# tests/adapters/exporters/test_json_exporter.py

"""Tests for JSON export functionality"""

# Standard library imports
import json
from os import remove
from os.path import exists
from pathlib import Path
from tempfile import NamedTemporaryFile

# Local imports
from marc_pd_tool.adapters.exporters.json_exporter import save_matches_json


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
            assert pub1["analysis"]["status"] == "US_REGISTERED_NOT_RENEWED"
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

    def test_json_export_compressed(self, sample_publications):
        """Test JSON export with gzip compression"""
        # Standard library imports
        import gzip

        with NamedTemporaryFile(suffix=".json", delete=False) as f:
            output_path = f.name

        try:
            save_matches_json(sample_publications, output_path, compress=True)

            # Verify .gz file was created
            gz_path = f"{output_path}.gz"
            assert exists(gz_path)

            # Load and verify compressed JSON
            with gzip.open(gz_path, "rt", encoding="utf-8") as f:
                data = json.load(f)

            assert data["metadata"]["total_records"] == 3
            assert len(data["records"]) == 3

        finally:
            gz_path = f"{output_path}.gz"
            if exists(gz_path):
                remove(gz_path)
            if exists(output_path):
                remove(output_path)

    def test_json_export_compressed_no_pretty(self, sample_publications):
        """Test compressed JSON export without pretty printing"""
        # Standard library imports
        import gzip

        with NamedTemporaryFile(suffix=".json", delete=False) as f:
            output_path = f.name

        try:
            save_matches_json(sample_publications, output_path, pretty=False, compress=True)

            gz_path = f"{output_path}.gz"
            assert exists(gz_path)

            # Load and check it's not pretty printed
            with gzip.open(gz_path, "rt", encoding="utf-8") as f:
                content = f.read()

            # Should be single line (no newlines in content)
            assert "\n" not in content.strip()

            # Verify it's still valid JSON
            data = json.loads(content)
            assert data["metadata"]["total_records"] == 3

        finally:
            gz_path = f"{output_path}.gz"
            if exists(gz_path):
                remove(gz_path)

    def test_json_export_with_parameters(self, sample_publications):
        """Test JSON export includes parameters in metadata"""
        with NamedTemporaryFile(suffix=".json", delete=False) as f:
            output_path = f.name

        parameters = {
            "title_threshold": 85,
            "author_threshold": 75,
            "year_tolerance": 2,
            "us_only": True,
        }

        try:
            save_matches_json(sample_publications, output_path, parameters=parameters)

            with open(output_path, "r") as f:
                data = json.load(f)

            # Check parameters are included in metadata
            assert "parameters" in data["metadata"]
            assert data["metadata"]["parameters"]["title_threshold"] == 85
            assert data["metadata"]["parameters"]["author_threshold"] == 75
            assert data["metadata"]["parameters"]["year_tolerance"] == 2
            assert data["metadata"]["parameters"]["us_only"] is True

        finally:
            if exists(output_path):
                remove(output_path)

    def test_json_export_lccn_match_type_counting(self, sample_publications):
        """Test that LCCN match types are counted correctly"""
        # Modify sample publications to have LCCN match type
        # Local imports
        from marc_pd_tool.core.domain.enums import MatchType

        # Set first publication to have LCCN match
        sample_publications[0].registration_match.match_type = MatchType.LCCN

        # Second has similarity match (default)
        # Third has no match
        sample_publications[2].registration_match = None
        sample_publications[2].renewal_match = None

        with NamedTemporaryFile(suffix=".json", delete=False) as f:
            output_path = f.name

        try:
            save_matches_json(sample_publications, output_path)

            with open(output_path, "r") as f:
                data = json.load(f)

            # Check match type counts
            counts = data["metadata"]["match_type_counts"]
            assert counts["lccn_matches"] == 1
            assert counts["similarity_matches"] == 1
            assert counts["no_matches"] == 1

        finally:
            if exists(output_path):
                remove(output_path)

    def test_publication_to_dict_function(self, sample_publications):
        """Test the _publication_to_dict function coverage"""
        # Local imports
        from marc_pd_tool.adapters.exporters.json_exporter import _publication_to_dict

        pub = sample_publications[0]

        # Test with both registration and renewal matches
        result = _publication_to_dict(pub)

        assert result["marc_record"]["id"] == "123"
        assert result["marc_record"]["title"] == "Test Book One"
        assert result["marc_record"]["author_245c"] == "Test Author One"
        assert result["marc_record"]["year"] == 1950
        assert result["marc_record"]["lccn"] == "50012345"
        assert result["marc_record"]["normalized_lccn"] == "50000001"
        assert result["marc_record"]["language_code"] == "eng"
        assert result["marc_record"]["country_code"] == "xxu"
        assert result["marc_record"]["country_classification"] == "US"

        assert result["analysis"]["copyright_status"] == "US_REGISTERED_NOT_RENEWED"
        assert result["analysis"]["generic_title_detected"] is False

        assert "registration_match" in result
        assert result["registration_match"]["source_id"] == "REG123"
        assert result["registration_match"]["title"] == "Test Book One"
        assert result["registration_match"]["scores"]["overall"] == 95.0
        assert result["registration_match"]["match_type"] == "similarity"

        # Test with no matches
        pub_no_match = sample_publications[2]
        pub_no_match.registration_match = None
        pub_no_match.renewal_match = None

        result = _publication_to_dict(pub_no_match)
        assert "registration_match" not in result
        assert "renewal_match" not in result

    def test_publication_to_dict_with_renewal_only(self, sample_publications):
        """Test _publication_to_dict with only renewal match"""
        # Local imports
        from marc_pd_tool.adapters.exporters.json_exporter import _publication_to_dict

        pub = sample_publications[1]
        pub.registration_match = None  # Remove registration match

        result = _publication_to_dict(pub)

        assert "registration_match" not in result
        assert "renewal_match" in result
        assert result["renewal_match"]["source_id"] == "REN456"
        assert result["renewal_match"]["title"] == "Test Book Two"
