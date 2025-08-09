# marc_pd_tool/api/_results.py

"""Analysis results container with export capabilities"""

# Standard library imports
from logging import getLogger
from os import unlink
from pickle import load
from tempfile import NamedTemporaryFile
from typing import cast

# Local imports
from marc_pd_tool.data.ground_truth import GroundTruthAnalysis
from marc_pd_tool.data.ground_truth import GroundTruthPair
from marc_pd_tool.data.ground_truth import GroundTruthStats
from marc_pd_tool.data.publication import Publication
from marc_pd_tool.exporters.csv_exporter import CSVExporter
from marc_pd_tool.exporters.html_exporter import HTMLExporter
from marc_pd_tool.exporters.json_exporter import save_matches_json
from marc_pd_tool.exporters.xlsx_exporter import XLSXExporter

logger = getLogger(__name__)


class AnalysisResults:
    """Container for analysis results with statistics and export capabilities"""

    def __init__(self) -> None:
        """Initialize empty results container"""
        self.publications: list[Publication] = []
        self.result_file_paths: list[str] = []  # Store paths to result pickle files
        self.result_files: dict[str, str] = {}  # Store exported file paths by format
        self.statistics: dict[str, int] = {
            "total_records": 0,
            "us_records": 0,
            "non_us_records": 0,
            "unknown_country": 0,
            "registration_matches": 0,
            "renewal_matches": 0,
            "no_matches": 0,
            "pd_pre_min_year": 0,
            "pd_us_not_renewed": 0,
            "pd_us_no_reg_data": 0,
            "pd_us_reg_no_renewal": 0,
            "unknown_us_no_data": 0,
            "in_copyright": 0,
            "in_copyright_us_renewed": 0,
            "research_us_status": 0,
            "research_us_only_pd": 0,
            "country_unknown": 0,
            "skipped_no_year": 0,
        }
        self.ground_truth_analysis: GroundTruthAnalysis | None = None
        self.ground_truth_pairs: list[GroundTruthPair] | None = None
        self.ground_truth_stats: GroundTruthStats | None = None
        self.result_temp_dir: str | None = None  # Temporary directory containing result files

    def add_publication(self, pub: Publication) -> None:
        """Add a publication to results and update statistics"""
        self.publications.append(pub)
        self._update_statistics(pub)

    def add_result_file(self, *args: str) -> None:
        """Add a result file path

        Can be called with either:
        - Single argument: file_path (for backward compatibility)
        - Two arguments: format_name, file_path (for new API)
        """
        if len(args) == 1:
            # Backward compatibility: single file path
            self.result_file_paths.append(args[0])
        elif len(args) == 2:
            # New API: format name and file path
            format_name, file_path = args
            self.result_files[format_name] = file_path
        else:
            raise ValueError("add_result_file expects 1 or 2 arguments")

    def update_statistics_from_batch(self, publications: list[Publication]) -> None:
        """Update statistics from a batch of publications without storing them"""
        for pub in publications:
            self._update_statistics(pub)

    def _update_statistics(self, pub: Publication) -> None:
        """Update statistics based on publication"""
        self.statistics["total_records"] += 1

        # Country classification
        if hasattr(pub, "country_classification"):
            if pub.country_classification.value == "US":
                self.statistics["us_records"] += 1
            elif pub.country_classification.value == "Non-US":
                self.statistics["non_us_records"] += 1
            else:
                self.statistics["unknown_country"] += 1

        # Match statistics
        has_any_match = False
        if pub.has_registration_match():
            self.statistics["registration_matches"] += 1
            has_any_match = True
        if pub.has_renewal_match():
            self.statistics["renewal_matches"] += 1
            has_any_match = True

        # Track records with no matches
        if not has_any_match:
            self.statistics["no_matches"] = self.statistics.get("no_matches", 0) + 1

        # Copyright status - dynamically track any status
        if hasattr(pub, "copyright_status") and pub.copyright_status:
            status_key = pub.copyright_status.lower()
            self.statistics[status_key] = self.statistics.get(status_key, 0) + 1

    def load_all_publications(self) -> None:
        """Load all publications from stored pickle files"""
        if not self.result_file_paths:
            return

        logger.info(f"Loading {len(self.result_file_paths)} result files...")

        for file_path in self.result_file_paths:
            try:
                with open(file_path, "rb") as f:
                    batch = cast(list[Publication], load(f))
                    self.publications.extend(batch)
            except Exception as e:
                logger.error(f"Failed to load result file {file_path}: {e}")

        logger.info(f"Loaded {len(self.publications)} publications from disk")

    def export_json(self, output_path: str, pretty: bool = True, compress: bool = False) -> None:
        """Export results to JSON format

        Args:
            output_path: Path for output JSON file
            pretty: Format JSON with indentation
            compress: Use gzip compression
        """
        # Ensure all publications are loaded
        self.load_all_publications()

        # Use the existing JSON exporter

        # Convert statistics dict to compatible type
        parameters: dict[str, str | int | float | bool] = {}
        for key, value in self.statistics.items():
            parameters[f"stat_{key}"] = value

        save_matches_json(
            self.publications, output_path, pretty=pretty, compress=compress, parameters=parameters
        )

    def export_csv(self, output_prefix: str) -> None:
        """Export results to CSV format

        Args:
            output_prefix: Prefix for output CSV files
        """
        # First export to JSON
        with NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
            json_path = tmp.name
            self.export_json(json_path)

        # Use the JSON-based CSV exporter

        exporter = CSVExporter(json_path, output_prefix)
        exporter.export()

        # Clean up temp file
        unlink(json_path)

    def export_xlsx(self, output_path: str) -> None:
        """Export results to XLSX format

        Args:
            output_path: Path for output XLSX file
        """
        # First export to JSON
        with NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
            json_path = tmp.name
            self.export_json(json_path)

        # Use the JSON-based XLSX exporter

        exporter = XLSXExporter(json_path, output_path)
        exporter.export()

        # Clean up temp file
        unlink(json_path)

    def export_html(self, output_dir: str) -> None:
        """Export results to HTML format

        Args:
            output_dir: Directory for HTML output
        """
        # First export to JSON
        with NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
            json_path = tmp.name
            self.export_json(json_path)

        # Use the JSON-based HTML exporter

        exporter = HTMLExporter(json_path, output_dir)
        exporter.export()

        # Clean up temp file
        unlink(json_path)

    def export_all(self, output_path: str) -> dict[str, str]:
        """Export results to all available formats

        Args:
            output_path: Base path for output files

        Returns:
            Dictionary mapping format names to output file paths
        """
        result_paths = {}

        # JSON export
        try:
            json_path = f"{output_path}.json"
            self.export_json(json_path)
            result_paths["json"] = json_path
        except Exception as e:
            logger.error(f"Failed to export JSON: {e}")

        # CSV export (creates multiple files)
        try:
            self.export_csv(output_path)
            result_paths["csv"] = output_path
        except Exception as e:
            logger.error(f"Failed to export CSV: {e}")

        # XLSX export
        try:
            xlsx_path = f"{output_path}.xlsx"
            self.export_xlsx(xlsx_path)
            result_paths["xlsx"] = xlsx_path
        except Exception as e:
            logger.error(f"Failed to export XLSX: {e}")

        # HTML export
        try:
            html_dir = f"{output_path}_html"
            self.export_html(html_dir)
            result_paths["html"] = html_dir
        except Exception as e:
            logger.error(f"Failed to export HTML: {e}")

        return result_paths
