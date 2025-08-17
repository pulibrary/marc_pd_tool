# marc_pd_tool/adapters/api/_ground_truth.py

"""Ground truth component for LCCN-based ground truth analysis"""

# Standard library imports
from json import dump
from logging import getLogger
from typing import TYPE_CHECKING

# Local imports
from marc_pd_tool.application.models.ground_truth_stats import GroundTruthStats
from marc_pd_tool.application.processing.ground_truth_extractor import (
    GroundTruthExtractor,
)
from marc_pd_tool.core.domain.publication import Publication
from marc_pd_tool.core.types.protocols import GroundTruthAnalyzerProtocol
from marc_pd_tool.infrastructure.persistence import MarcLoader

if TYPE_CHECKING:
    # Local imports
    pass

logger = getLogger(__name__)


class GroundTruthComponent:
    """Component for ground truth extraction and analysis"""

    def extract_ground_truth(
        self: GroundTruthAnalyzerProtocol,
        marc_path: str,
        copyright_dir: str | None = None,
        renewal_dir: str | None = None,
        min_year: int | None = None,
        max_year: int | None = None,
    ) -> tuple[list[Publication], GroundTruthStats]:
        """Extract LCCN-verified ground truth pairs

        Args:
            marc_path: Path to MARC XML file
            copyright_dir: Directory containing copyright XML files
            renewal_dir: Directory containing renewal TSV files
            min_year: Minimum publication year filter
            max_year: Maximum publication year filter

        Returns:
            Tuple of (marc_publications_with_lccn_matches, statistics)
        """
        # Set data directories
        if copyright_dir:
            self.copyright_dir = copyright_dir
        if renewal_dir:
            self.renewal_dir = renewal_dir

        # Load MARC data
        logger.info(f"Loading MARC records from {marc_path}")
        # Use batch_size from config like other modes
        processing_config = self.config.processing
        batch_size = processing_config.batch_size
        marc_loader = MarcLoader(
            marc_path=marc_path, batch_size=batch_size, min_year=min_year, max_year=max_year
        )

        # Load copyright and renewal data if not already loaded
        if not self.copyright_data or not self.renewal_data:
            # Local imports
            from marc_pd_tool.application.models.config_models import AnalysisOptions

            self._load_and_index_data(AnalysisOptions(min_year=min_year, max_year=max_year))

        # If indexes were loaded from cache, extract the publications from them
        if self.registration_index and not self.copyright_data:
            self.copyright_data = self.registration_index.publications

        if self.renewal_index and not self.renewal_data:
            self.renewal_data = self.renewal_index.publications

        # Extract ground truth pairs
        extractor = GroundTruthExtractor()
        marc_batches = marc_loader.extract_all_batches()
        ground_truth_pairs, stats = extractor.extract_ground_truth_pairs(
            marc_batches, self.copyright_data or [], self.renewal_data
        )

        # Apply filters if specified
        if min_year is not None or max_year is not None:
            ground_truth_pairs = extractor.filter_by_year_range(
                ground_truth_pairs, min_year, max_year
            )

        # Store in results
        self.results.ground_truth_pairs = ground_truth_pairs
        self.results.ground_truth_stats = stats

        return ground_truth_pairs, stats

    def export_ground_truth_analysis(
        self: GroundTruthAnalyzerProtocol,
        output_path: str,
        output_formats: list[str] | None = None,
        output_format: str | None = None,
    ) -> None:
        """Export ground truth analysis results

        Args:
            output_path: Path for output file
            output_formats: List of output formats (['csv', 'xlsx', 'json', 'html'])
            output_format: Single output format (deprecated, use output_formats)
        """
        # Handle backward compatibility
        if output_formats is None:
            if output_format is not None:
                output_formats = [output_format]
            else:
                output_formats = ["csv"]

        if not self.results.ground_truth_pairs:
            raise ValueError("No ground truth pairs available to export")

        logger.info(f"Exporting ground truth analysis to {output_path}")

        for fmt in output_formats:
            if fmt.lower() == "json":
                self._export_ground_truth_json(output_path)
            elif fmt.lower() == "csv":
                self._export_ground_truth_csv(output_path)
            elif fmt.lower() == "xlsx":
                # TODO: Implement XLSX export for ground truth
                logger.warning("XLSX export for ground truth not yet implemented")
            elif fmt.lower() == "html":
                # TODO: Implement HTML export for ground truth
                logger.warning("HTML export for ground truth not yet implemented")
            else:
                logger.warning(f"Unknown export format: {fmt}")

    def _export_ground_truth_json(self: GroundTruthAnalyzerProtocol, output_path: str) -> None:
        """Export ground truth pairs as JSON"""
        if not self.results.ground_truth_pairs:
            raise ValueError("No ground truth pairs available")

        pairs = self.results.ground_truth_pairs
        stats = self.results.ground_truth_stats

        # Convert to JSON-serializable format
        json_data = {
            "statistics": {
                "total_marc_records": stats.total_marc_records if stats else 0,
                "marc_with_lccn": stats.marc_with_lccn if stats else 0,
                "marc_lccn_coverage": stats.marc_lccn_coverage if stats else 0.0,
                "total_pairs": len(pairs),
                "registration_matches": stats.registration_matches if stats else 0,
                "renewal_matches": stats.renewal_matches if stats else 0,
                "unique_lccns": stats.unique_lccns if stats else 0,
            },
            "ground_truth_pairs": [
                {
                    "marc_record": {
                        "id": marc.source_id,
                        "title": marc.title,
                        "author": marc.author,
                        "year": marc.year,
                        "publisher": marc.publisher,
                        "lccn": marc.lccn,
                    },
                    "matches": (
                        [
                            {
                                "match_type": "registration",
                                "title": marc.registration_match.matched_title,
                                "author": marc.registration_match.matched_author,
                                "publisher": marc.registration_match.matched_publisher,
                                "source_id": marc.registration_match.source_id,
                                "scores": {
                                    "title": marc.registration_match.title_score,
                                    "author": marc.registration_match.author_score,
                                    "publisher": marc.registration_match.publisher_score,
                                    "combined": marc.registration_match.similarity_score,
                                },
                            }
                            for marc in [marc]
                            if marc.registration_match
                        ]
                        + [
                            {
                                "match_type": "renewal",
                                "title": marc.renewal_match.matched_title,
                                "author": marc.renewal_match.matched_author,
                                "publisher": marc.renewal_match.matched_publisher,
                                "source_id": marc.renewal_match.source_id,
                                "scores": {
                                    "title": marc.renewal_match.title_score,
                                    "author": marc.renewal_match.author_score,
                                    "publisher": marc.renewal_match.publisher_score,
                                    "combined": marc.renewal_match.similarity_score,
                                },
                            }
                            for marc in [marc]
                            if marc.renewal_match
                        ]
                    ),
                }
                for marc in pairs
            ],
        }

        # Write to file
        json_path = f"{output_path}.json" if not output_path.endswith(".json") else output_path
        with open(json_path, "w") as f:
            dump(json_data, f, indent=2)

        logger.info(f"✓ Exported ground truth analysis to {json_path}")

    def _export_ground_truth_csv(self: GroundTruthAnalyzerProtocol, output_path: str) -> None:
        """Export ground truth pairs as CSV using the new unified structure"""
        # Local imports
        from marc_pd_tool.adapters.exporters.ground_truth_csv_exporter import (
            export_ground_truth_csv,
        )

        if not self.results.ground_truth_pairs:
            logger.warning("No ground truth pairs available for CSV export")
            return

        export_ground_truth_csv(self.results.ground_truth_pairs, output_path)
