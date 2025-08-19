# tests/adapters/api/test_api_export.py

"""Tests for export functionality in the API module"""

# Standard library imports
from json import load
from unittest.mock import Mock
from unittest.mock import patch

# Third party imports
from pytest import fixture
from pytest import raises

# Local imports
from marc_pd_tool.adapters.api import AnalysisResults
from marc_pd_tool.core.domain.enums import CopyrightStatus
from marc_pd_tool.core.domain.enums import CountryClassification
from marc_pd_tool.core.domain.enums import MatchType
from marc_pd_tool.core.domain.match_result import MatchResult
from marc_pd_tool.core.domain.publication import Publication


class TestAnalysisResultsExport:
    """Test AnalysisResults export methods"""

    @fixture
    def sample_results(self):
        """Create sample analysis results for testing"""
        results = AnalysisResults()

        # Add some test publications with different statuses
        pub1 = Publication(
            title="Public Domain Book",
            author="PD Author",
            pub_date="1940",
            source_id="001",
            country_code="xxu",
            country_classification=CountryClassification.US,
        )
        pub1.copyright_status = CopyrightStatus.US_REGISTERED_NOT_RENEWED.value

        pub2 = Publication(
            title="Copyrighted Book",
            author="Copyright Author",
            pub_date="1950",
            source_id="002",
            country_code="xxu",
            country_classification=CountryClassification.US,
        )
        pub2.copyright_status = CopyrightStatus.US_RENEWED.value

        pub3 = Publication(
            title="Research Needed",
            author="Unknown Status",
            pub_date="1965",
            source_id="003",
            country_code="xxu",
            country_classification=CountryClassification.US,
        )
        pub3.copyright_status = CopyrightStatus.US_NO_MATCH.value

        results.add_publication(pub1)
        results.add_publication(pub2)
        results.add_publication(pub3)

        # Set some statistics (they're already set by add_publication, but override for test)
        results.statistics.total_records = 3
        results.statistics.us_records = 3
        results.statistics.non_us_records = 0
        results.statistics.registration_matches = 1
        results.statistics.renewal_matches = 0
        results.statistics.pd_us_not_renewed = 1
        results.statistics.in_copyright = 1
        results.statistics.research_us_status = 1

        return results

    def test_export_json(self, sample_results, tmp_path):
        """Test JSON export functionality"""
        output_file = tmp_path / "results.json"

        sample_results.export_json(str(output_file))

        assert output_file.exists()

        with open(output_file) as f:
            data = load(f)

        assert "metadata" in data
        assert "records" in data
        assert len(data["records"]) == 3
        assert data["metadata"]["parameters"]["stat_total_records"] == 3

    def test_export_csv(self, sample_results, tmp_path):
        """Test CSV export functionality"""
        output_prefix = str(tmp_path / "results")

        # Mock the CSV exporter where it's actually imported
        with patch("marc_pd_tool.application.models.analysis_results.CSVExporter") as mock_csv:
            mock_exporter = Mock()
            mock_csv.return_value = mock_exporter

            sample_results.export_csv(output_prefix)

            # Verify exporter was created correctly (with JSON path and output path)
            # The exporter is now created with a temp JSON file
            assert mock_csv.called
            mock_exporter.export.assert_called_once()

    def test_export_xlsx(self, sample_results, tmp_path):
        """Test XLSX export functionality"""
        output_file = str(tmp_path / "results.xlsx")

        # Mock the XLSX exporter where it's actually imported
        with patch("marc_pd_tool.application.models.analysis_results.XLSXExporter") as mock_xlsx:
            mock_exporter = Mock()
            mock_xlsx.return_value = mock_exporter

            sample_results.export_xlsx(output_file)

            # Verify exporter was created correctly (with JSON path and output path)
            # The exporter is now created with a temp JSON file
            assert mock_xlsx.called
            mock_exporter.export.assert_called_once()

    def test_export_html(self, sample_results, tmp_path):
        """Test HTML export functionality"""
        output_dir = str(tmp_path / "html_output")

        # Mock the HTML exporter where it's actually imported
        with patch("marc_pd_tool.application.models.analysis_results.HTMLExporter") as mock_html:
            mock_exporter = Mock()
            mock_html.return_value = mock_exporter

            sample_results.export_html(output_dir)

            # Verify exporter was created correctly (with JSON path and output path)
            # The exporter is now created with a temp JSON file
            assert mock_html.called
            mock_exporter.export.assert_called_once()

    def test_export_all(self, sample_results, tmp_path):
        """Test export_all method that exports to all formats"""
        output_path = str(tmp_path / "all_formats")

        # Mock all exporters and the export_json method
        with (
            patch("marc_pd_tool.application.models.analysis_results.CSVExporter") as mock_csv,
            patch("marc_pd_tool.application.models.analysis_results.XLSXExporter") as mock_xlsx,
            patch("marc_pd_tool.application.models.analysis_results.HTMLExporter") as mock_html,
            patch(
                "marc_pd_tool.application.models.analysis_results.save_matches_json"
            ) as mock_save_json,
        ):

            mock_csv_exporter = Mock()
            mock_xlsx_exporter = Mock()
            mock_html_exporter = Mock()

            mock_csv.return_value = mock_csv_exporter
            mock_xlsx.return_value = mock_xlsx_exporter
            mock_html.return_value = mock_html_exporter

            result_paths = sample_results.export_all(output_path)

            # Verify all exporters were called
            # save_matches_json is called multiple times (once for main export, once for each format)
            assert mock_save_json.call_count >= 4  # Main + CSV + XLSX + HTML
            mock_csv_exporter.export.assert_called_once()
            mock_xlsx_exporter.export.assert_called_once()
            mock_html_exporter.export.assert_called_once()

            # Verify return value
            assert "json" in result_paths
            assert "csv" in result_paths
            assert "xlsx" in result_paths
            assert "html" in result_paths

    def test_add_result_file(self, sample_results):
        """Test adding result file paths"""
        sample_results.add_result_file("csv", "/path/to/result.csv")
        sample_results.add_result_file("xlsx", "/path/to/result.xlsx")

        assert sample_results.result_files["csv"] == "/path/to/result.csv"
        assert sample_results.result_files["xlsx"] == "/path/to/result.xlsx"

    def test_export_json_with_matches(self, tmp_path):
        """Test JSON export with match information"""
        results = AnalysisResults()

        # Create publication with matches
        pub = Publication(
            title="Matched Book", author="Matched Author", pub_date="1950", source_id="001"
        )

        # Add registration match
        pub.registration_match = MatchResult(
            matched_title="Matched Book",
            matched_author="Matched Author",
            similarity_score=92.0,
            title_score=95.0,
            author_score=90.0,
            year_difference=0,
            source_id="C001",
            source_type="registration",
            matched_date="1950",
            match_type=MatchType.SIMILARITY,
        )

        pub.copyright_status = CopyrightStatus.US_RENEWED.value
        results.add_publication(pub)

        output_file = tmp_path / "matched.json"
        results.export_json(str(output_file))

        with open(output_file) as f:
            data = load(f)

        assert len(data["records"]) == 1
        record = data["records"][0]
        # Check for registration match in the comprehensive format
        assert record["matches"]["registration"]["found"] is True
        assert record["matches"]["registration"]["scores"]["title"] == 95.0


class TestMarcCopyrightAnalyzerExport:
    """Test export methods in MarcCopyrightAnalyzer"""

    pass


class TestExportErrorHandling:
    """Test error handling in export methods"""

    @fixture
    def sample_results(self):
        """Create sample analysis results for testing"""
        results = AnalysisResults()

        # Add a simple test publication
        pub = Publication(title="Test Book", author="Test Author", pub_date="1950", source_id="001")
        pub.copyright_status = CopyrightStatus.US_REGISTERED_NOT_RENEWED.value
        results.add_publication(pub)

        return results

    def test_export_json_io_error(self, sample_results):
        """Test JSON export with I/O error"""
        with patch("builtins.open", side_effect=IOError("Disk full")):
            with raises(IOError):
                sample_results.export_json("/invalid/path/results.json")

    def test_export_all_partial_failure(self, sample_results, tmp_path):
        """Test export_all when one format fails"""
        output_path = str(tmp_path / "partial")

        # Mock exporters with one failure
        with (
            patch("marc_pd_tool.application.models.analysis_results.CSVExporter") as mock_csv,
            patch("marc_pd_tool.application.models.analysis_results.XLSXExporter") as mock_xlsx,
            patch("marc_pd_tool.application.models.analysis_results.HTMLExporter") as mock_html,
            patch(
                "marc_pd_tool.application.models.analysis_results.save_matches_json"
            ) as mock_save_json,
        ):

            mock_csv_exporter = Mock()
            mock_xlsx_exporter = Mock()
            mock_html_exporter = Mock()

            # Make XLSX export fail
            mock_xlsx_exporter.export.side_effect = Exception("XLSX export failed")

            mock_csv.return_value = mock_csv_exporter
            mock_xlsx.return_value = mock_xlsx_exporter
            mock_html.return_value = mock_html_exporter

            # Should continue despite one failure
            result_paths = sample_results.export_all(output_path)

            # Other exports should still be called
            # save_matches_json is called multiple times (once for main export, once for each format)
            assert mock_save_json.call_count >= 3  # Main + CSV + HTML (XLSX failed)
            mock_csv_exporter.export.assert_called_once()
            mock_html_exporter.export.assert_called_once()

            # XLSX should not be in results due to failure
            assert "xlsx" not in result_paths
            assert "json" in result_paths
            assert "csv" in result_paths
            assert "html" in result_paths
