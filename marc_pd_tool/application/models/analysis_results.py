# marc_pd_tool/application/models/analysis_results.py

"""Pydantic model for analysis results container"""

# Standard library imports
from logging import getLogger
from os import unlink
from pickle import load
from tempfile import NamedTemporaryFile
from typing import cast

# Third party imports
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import computed_field

# Local imports
from marc_pd_tool.adapters.exporters.csv_exporter import CSVExporter
from marc_pd_tool.adapters.exporters.html_exporter import HTMLExporter
from marc_pd_tool.adapters.exporters.json_exporter import save_matches_json
from marc_pd_tool.adapters.exporters.xlsx_exporter import XLSXExporter
from marc_pd_tool.application.models.ground_truth_stats import GroundTruthStats
from marc_pd_tool.core.domain.publication import Publication

logger = getLogger(__name__)


class AnalysisStatistics(BaseModel):
    """Statistics about the analysis results"""

    model_config = ConfigDict()

    total_records: int = 0
    us_records: int = 0
    non_us_records: int = 0
    unknown_country: int = 0
    registration_matches: int = 0
    renewal_matches: int = 0
    no_matches: int = 0
    pd_pre_min_year: int = 0
    pd_us_not_renewed: int = 0
    pd_us_no_reg_data: int = 0
    pd_us_reg_no_renewal: int = 0
    unknown_us_no_data: int = 0
    in_copyright: int = 0
    in_copyright_us_renewed: int = 0
    research_us_status: int = 0
    research_us_only_pd: int = 0
    country_unknown: int = 0
    skipped_no_year: int = 0

    # Allow dynamic fields for copyright status tracking
    extra_fields: dict[str, int] = Field(default_factory=dict)

    def increment(self, field: str, value: int = 1) -> None:
        """Increment a statistic field by value

        Args:
            field: Field name to increment
            value: Amount to increment by (default 1)
        """
        if hasattr(self, field):
            current = getattr(self, field)
            setattr(self, field, current + value)
        else:
            # Store in extra_fields for dynamic statuses
            self.extra_fields[field] = self.extra_fields.get(field, 0) + value

    def get(self, field: str, default: int = 0) -> int:
        """Get a statistic value with default

        Args:
            field: Field name to get
            default: Default value if field doesn't exist

        Returns:
            Field value or default
        """
        if hasattr(self, field):
            return getattr(self, field)
        return self.extra_fields.get(field, default)

    def to_dict(self) -> dict[str, int]:
        """Convert statistics to dictionary

        Returns:
            Dictionary of all statistics
        """
        result = self.model_dump(exclude={"extra_fields"})
        result.update(self.extra_fields)
        return result


class AnalysisResults(BaseModel):
    """Container for analysis results with statistics and export capabilities"""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    publications: list[Publication] = Field(default_factory=list)
    result_file_paths: list[str] = Field(default_factory=list)
    result_files: dict[str, str] = Field(default_factory=dict)
    statistics: AnalysisStatistics = Field(default_factory=AnalysisStatistics)
    ground_truth_pairs: list[Publication] | None = None
    ground_truth_stats: GroundTruthStats | None = None
    result_temp_dir: str | None = None

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

    def cleanup_temp_files(self) -> None:
        """Clean up temporary result files and directory"""
        if self.result_temp_dir:
            # Standard library imports
            from pathlib import Path
            import shutil

            temp_path = Path(self.result_temp_dir)
            if temp_path.exists():
                try:
                    shutil.rmtree(temp_path)
                    logger.debug(f"Cleaned up temporary directory: {self.result_temp_dir}")
                except Exception as e:
                    logger.warning(f"Failed to clean up temp directory {self.result_temp_dir}: {e}")

            self.result_temp_dir = None
            self.result_file_paths.clear()

    def update_statistics_from_batch(self, publications: list[Publication]) -> None:
        """Update statistics from a batch of publications without storing them"""
        for pub in publications:
            self._update_statistics(pub)

    def _update_statistics(self, pub: Publication) -> None:
        """Update statistics based on publication"""
        self.statistics.increment("total_records")

        # Country classification
        if hasattr(pub, "country_classification"):
            if pub.country_classification.value == "US":
                self.statistics.increment("us_records")
            elif pub.country_classification.value == "Non-US":
                self.statistics.increment("non_us_records")
            else:
                self.statistics.increment("unknown_country")

        # Match statistics
        has_any_match = False
        if pub.has_registration_match():
            self.statistics.increment("registration_matches")
            has_any_match = True
        if pub.has_renewal_match():
            self.statistics.increment("renewal_matches")
            has_any_match = True

        # Track records with no matches
        if not has_any_match:
            self.statistics.increment("no_matches")

        # Copyright status - dynamically track any status
        if hasattr(pub, "copyright_status") and pub.copyright_status:
            status_key = pub.copyright_status.lower()
            self.statistics.increment(status_key)

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

        # Convert statistics dict to compatible type
        parameters: dict[str, str | int | float | bool] = {}
        for key, value in self.statistics.to_dict().items():
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

    @computed_field  # type: ignore[misc]
    @property
    def match_rate(self) -> float:
        """Calculate the match rate as a percentage"""
        total = self.statistics.total_records
        if total == 0:
            return 0.0
        matches = self.statistics.registration_matches + self.statistics.renewal_matches
        return (matches / total) * 100

    @computed_field  # type: ignore[misc]
    @property
    def public_domain_rate(self) -> float:
        """Calculate the public domain rate as a percentage"""
        total = self.statistics.total_records
        if total == 0:
            return 0.0
        pd_count = (
            self.statistics.pd_pre_min_year
            + self.statistics.pd_us_not_renewed
            + self.statistics.pd_us_no_reg_data
            + self.statistics.pd_us_reg_no_renewal
        )
        return (pd_count / total) * 100
