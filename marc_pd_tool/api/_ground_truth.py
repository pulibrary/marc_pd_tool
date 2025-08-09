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

    def _export_ground_truth_csv(self: GroundTruthAnalyzerProtocol, output_path: str) -> None:
        """Export comprehensive ground truth CSV with all data versions

        This CSV includes original, normalized, and stemmed versions of all fields
        for detailed analysis of the matching algorithm.
        """
        # Standard library imports
        import csv
        from os.path import splitext

        # Local imports
        from marc_pd_tool.processing.text_processing import LanguageProcessor
        from marc_pd_tool.processing.text_processing import MultiLanguageStemmer
        from marc_pd_tool.utils.text_utils import normalize_text_standard

        if not self.results.ground_truth_pairs:
            logger.warning("No ground truth pairs available for CSV export")
            return

        # Ensure .csv extension
        base_path = splitext(output_path)[0]
        csv_path = f"{base_path}.csv"

        # Create processors for text normalization
        language_processor = LanguageProcessor()
        stemmer = MultiLanguageStemmer()

        # Prepare CSV headers
        headers = [
            # MARC Record Data
            "marc_id",
            "marc_title_original",
            "marc_title_normalized",
            "marc_title_stemmed",
            "marc_author_original",
            "marc_author_normalized",
            "marc_author_stemmed",
            "marc_main_author_original",
            "marc_main_author_normalized",
            "marc_main_author_stemmed",
            "marc_publisher_original",
            "marc_publisher_normalized",
            "marc_publisher_stemmed",
            "marc_year",
            "marc_lccn",
            "marc_lccn_normalized",
            # Copyright/Renewal Data
            "match_type",  # "registration" or "renewal"
            "match_title_original",
            "match_title_normalized",
            "match_title_stemmed",
            "match_author_original",
            "match_author_normalized",
            "match_author_stemmed",
            "match_publisher_original",
            "match_publisher_normalized",
            "match_publisher_stemmed",
            "match_year",
            "match_lccn",
            "match_lccn_normalized",
            "match_entry_id",  # For renewals
            # Matching Scores
            "title_score",
            "author_score",
            "publisher_score",
            "combined_score",
            "year_difference",
            "copyright_status",
        ]

        # Write CSV
        with open(csv_path, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=headers)
            writer.writeheader()

            for pair in self.results.ground_truth_pairs:
                marc = pair.marc_record
                match = pair.copyright_record

                # Get match result if available
                match_result = None
                if marc.registration_match and pair.match_type == "registration":
                    match_result = marc.registration_match
                elif marc.renewal_match and pair.match_type == "renewal":
                    match_result = marc.renewal_match

                # Process MARC text fields
                marc_title_norm = (
                    normalize_text_standard(marc.original_title) if marc.original_title else ""
                )
                marc_title_words = (
                    language_processor.remove_stopwords(marc_title_norm) if marc_title_norm else []
                )
                marc_title_stem = (
                    " ".join(stemmer.stem_words(marc_title_words)) if marc_title_words else ""
                )

                marc_author_norm = (
                    normalize_text_standard(marc.original_author) if marc.original_author else ""
                )
                marc_author_words = (
                    language_processor.remove_stopwords(marc_author_norm)
                    if marc_author_norm
                    else []
                )
                marc_author_stem = (
                    " ".join(stemmer.stem_words(marc_author_words)) if marc_author_words else ""
                )

                marc_main_author_norm = (
                    normalize_text_standard(marc.original_main_author)
                    if marc.original_main_author
                    else ""
                )
                marc_main_author_words = (
                    language_processor.remove_stopwords(marc_main_author_norm)
                    if marc_main_author_norm
                    else []
                )
                marc_main_author_stem = (
                    " ".join(stemmer.stem_words(marc_main_author_words))
                    if marc_main_author_words
                    else ""
                )

                marc_publisher_norm = (
                    normalize_text_standard(marc.original_publisher)
                    if marc.original_publisher
                    else ""
                )
                marc_publisher_words = (
                    language_processor.remove_stopwords(marc_publisher_norm)
                    if marc_publisher_norm
                    else []
                )
                marc_publisher_stem = (
                    " ".join(stemmer.stem_words(marc_publisher_words))
                    if marc_publisher_words
                    else ""
                )

                # Process match text fields
                match_title_norm = (
                    normalize_text_standard(match.original_title) if match.original_title else ""
                )
                match_title_words = (
                    language_processor.remove_stopwords(match_title_norm)
                    if match_title_norm
                    else []
                )
                match_title_stem = (
                    " ".join(stemmer.stem_words(match_title_words)) if match_title_words else ""
                )

                match_author_norm = (
                    normalize_text_standard(match.original_author) if match.original_author else ""
                )
                match_author_words = (
                    language_processor.remove_stopwords(match_author_norm)
                    if match_author_norm
                    else []
                )
                match_author_stem = (
                    " ".join(stemmer.stem_words(match_author_words)) if match_author_words else ""
                )

                match_publisher_norm = (
                    normalize_text_standard(match.original_publisher)
                    if match.original_publisher
                    else ""
                )
                match_publisher_words = (
                    language_processor.remove_stopwords(match_publisher_norm)
                    if match_publisher_norm
                    else []
                )
                match_publisher_stem = (
                    " ".join(stemmer.stem_words(match_publisher_words))
                    if match_publisher_words
                    else ""
                )

                # Build row
                row = {
                    # MARC data
                    "marc_id": marc.source_id or "",
                    "marc_title_original": marc.original_title or "",
                    "marc_title_normalized": marc_title_norm,
                    "marc_title_stemmed": marc_title_stem,
                    "marc_author_original": marc.original_author or "",
                    "marc_author_normalized": marc_author_norm,
                    "marc_author_stemmed": marc_author_stem,
                    "marc_main_author_original": marc.original_main_author or "",
                    "marc_main_author_normalized": marc_main_author_norm,
                    "marc_main_author_stemmed": marc_main_author_stem,
                    "marc_publisher_original": marc.original_publisher or "",
                    "marc_publisher_normalized": marc_publisher_norm,
                    "marc_publisher_stemmed": marc_publisher_stem,
                    "marc_year": marc.year or "",
                    "marc_lccn": marc.lccn or "",
                    "marc_lccn_normalized": marc.normalized_lccn or "",
                    # Match data
                    "match_type": pair.match_type,
                    "match_title_original": match.original_title or "",
                    "match_title_normalized": match_title_norm,
                    "match_title_stemmed": match_title_stem,
                    "match_author_original": match.original_author or "",
                    "match_author_normalized": match_author_norm,
                    "match_author_stemmed": match_author_stem,
                    "match_publisher_original": match.original_publisher or "",
                    "match_publisher_normalized": match_publisher_norm,
                    "match_publisher_stemmed": match_publisher_stem,
                    "match_year": match.year or "",
                    "match_lccn": match.lccn or "",
                    "match_lccn_normalized": match.normalized_lccn or "",
                    "match_entry_id": "",  # Not available in Publication object
                    # Scores
                    "title_score": match_result.title_score if match_result else "",
                    "author_score": match_result.author_score if match_result else "",
                    "publisher_score": match_result.publisher_score if match_result else "",
                    "combined_score": match_result.similarity_score if match_result else "",
                    "year_difference": match_result.year_difference if match_result else "",
                    "copyright_status": (
                        marc.copyright_status.value
                        if hasattr(marc.copyright_status, "value")
                        else str(marc.copyright_status) if marc.copyright_status else ""
                    ),
                }

                writer.writerow(row)

        logger.info(
            f"✓ Exported ground truth CSV to {csv_path} ({len(self.results.ground_truth_pairs)} pairs)"
        )
