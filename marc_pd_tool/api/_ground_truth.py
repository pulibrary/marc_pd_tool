# marc_pd_tool/api/_ground_truth.py

"""Ground truth mixin for LCCN-based ground truth analysis"""

# Standard library imports
from json import dump
from logging import getLogger
from typing import Protocol
from typing import TYPE_CHECKING

# Local imports
from marc_pd_tool.data.ground_truth import GroundTruthAnalysis
from marc_pd_tool.data.ground_truth import GroundTruthPair
from marc_pd_tool.data.ground_truth import GroundTruthStats
from marc_pd_tool.data.publication import Publication
from marc_pd_tool.loaders.marc_loader import MarcLoader
from marc_pd_tool.processing.ground_truth_extractor import GroundTruthExtractor
from marc_pd_tool.processing.score_analyzer import ScoreAnalyzer
from marc_pd_tool.utils.types import JSONType

if TYPE_CHECKING:
    # Local imports
    from marc_pd_tool.api._results import AnalysisResults

logger = getLogger(__name__)


class GroundTruthAnalyzerProtocol(Protocol):
    """Protocol defining required attributes for GroundTruthMixin"""

    results: "AnalysisResults"
    copyright_dir: str
    renewal_dir: str
    copyright_data: list[Publication] | None
    renewal_data: list[Publication] | None

    def _load_and_index_data(self, options: dict[str, JSONType]) -> None: ...
    def _export_ground_truth_json(self, output_path: str) -> None: ...


class GroundTruthMixin:
    """Mixin for ground truth extraction and analysis"""

    def extract_ground_truth(
        self: GroundTruthAnalyzerProtocol,
        marc_path: str,
        copyright_dir: str | None = None,
        renewal_dir: str | None = None,
        min_year: int | None = None,
        max_year: int | None = None,
    ) -> tuple[list[GroundTruthPair], GroundTruthStats]:
        """Extract LCCN-verified ground truth pairs

        Args:
            marc_path: Path to MARC XML file
            copyright_dir: Directory containing copyright XML files
            renewal_dir: Directory containing renewal TSV files
            min_year: Minimum publication year filter
            max_year: Maximum publication year filter

        Returns:
            Tuple of (ground_truth_pairs, statistics)
        """
        # Set data directories
        if copyright_dir:
            self.copyright_dir = copyright_dir
        if renewal_dir:
            self.renewal_dir = renewal_dir

        # Load MARC data
        logger.info(f"Loading MARC records from {marc_path}")
        marc_loader = MarcLoader(
            marc_path=marc_path, batch_size=1000, min_year=min_year, max_year=max_year
        )

        # Load copyright and renewal data if not already loaded
        if not self.copyright_data or not self.renewal_data:
            self._load_and_index_data({"min_year": min_year, "max_year": max_year})

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

    def analyze_ground_truth_scores(
        self: GroundTruthAnalyzerProtocol, ground_truth_pairs: list[GroundTruthPair] | None = None
    ) -> GroundTruthAnalysis:
        """Analyze similarity scores for ground truth pairs

        Args:
            ground_truth_pairs: List of ground truth pairs (uses stored pairs if None)

        Returns:
            Complete analysis with score distributions
        """
        if ground_truth_pairs is None:
            ground_truth_pairs = self.results.ground_truth_pairs or []

        if not ground_truth_pairs:
            raise ValueError("No ground truth pairs available for analysis")

        # Analyze scores
        analyzer = ScoreAnalyzer()
        analysis = analyzer.analyze_ground_truth_scores(ground_truth_pairs)

        # Store in results
        self.results.ground_truth_analysis = analysis

        return analysis

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

        if not self.results.ground_truth_analysis:
            raise ValueError("No ground truth analysis available to export")

        logger.info(f"Exporting ground truth analysis to {output_path}")

        for fmt in output_formats:
            if fmt.lower() == "json":
                self._export_ground_truth_json(output_path)
            elif fmt.lower() == "csv":
                # TODO: Implement CSV export for ground truth
                logger.warning("CSV export for ground truth not yet implemented")
            elif fmt.lower() == "xlsx":
                # TODO: Implement XLSX export for ground truth
                logger.warning("XLSX export for ground truth not yet implemented")
            elif fmt.lower() == "html":
                # TODO: Implement HTML export for ground truth
                logger.warning("HTML export for ground truth not yet implemented")
            else:
                logger.warning(f"Unknown export format: {fmt}")

    def _export_ground_truth_json(self: GroundTruthAnalyzerProtocol, output_path: str) -> None:
        """Export ground truth analysis as JSON"""
        if not self.results.ground_truth_analysis:
            raise ValueError("No ground truth analysis available")

        analysis = self.results.ground_truth_analysis

        # Convert to JSON-serializable format
        json_data = {
            "statistics": {
                "total_pairs": analysis.total_pairs,
                "registration_pairs": analysis.registration_pairs,
                "renewal_pairs": analysis.renewal_pairs,
            },
            "score_distributions": {
                "title": {
                    "mean": analysis.title_distribution.mean_score,
                    "median": analysis.title_distribution.median_score,
                    "std": analysis.title_distribution.std_dev,
                    "min": analysis.title_distribution.min_score,
                    "max": analysis.title_distribution.max_score,
                    "percentile_25": analysis.title_distribution.percentile_25,
                    "percentile_75": analysis.title_distribution.percentile_75,
                },
                "author": {
                    "mean": analysis.author_distribution.mean_score,
                    "median": analysis.author_distribution.median_score,
                    "std": analysis.author_distribution.std_dev,
                    "min": analysis.author_distribution.min_score,
                    "max": analysis.author_distribution.max_score,
                    "percentile_25": analysis.author_distribution.percentile_25,
                    "percentile_75": analysis.author_distribution.percentile_75,
                },
                "publisher": {
                    "mean": analysis.publisher_distribution.mean_score,
                    "median": analysis.publisher_distribution.median_score,
                    "std": analysis.publisher_distribution.std_dev,
                    "min": analysis.publisher_distribution.min_score,
                    "max": analysis.publisher_distribution.max_score,
                    "percentile_25": analysis.publisher_distribution.percentile_25,
                    "percentile_75": analysis.publisher_distribution.percentile_75,
                },
                "combined": {
                    "mean": analysis.combined_distribution.mean_score,
                    "median": analysis.combined_distribution.median_score,
                    "std": analysis.combined_distribution.std_dev,
                    "min": analysis.combined_distribution.min_score,
                    "max": analysis.combined_distribution.max_score,
                    "percentile_25": analysis.combined_distribution.percentile_25,
                    "percentile_75": analysis.combined_distribution.percentile_75,
                },
            },
        }

        # Write to file
        json_path = f"{output_path}.json" if not output_path.endswith(".json") else output_path
        with open(json_path, "w") as f:
            dump(json_data, f, indent=2)

        logger.info(f"✓ Exported ground truth analysis to {json_path}")
