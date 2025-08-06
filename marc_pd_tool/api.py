# marc_pd_tool/api.py

"""High-level API for MARC copyright analysis

This module provides the main public API for the marc_pd_tool package,
offering a simplified interface for analyzing MARC records against
copyright and renewal data.
"""

# Standard library imports
from atexit import register
from atexit import unregister
from gc import get_stats as gc_get_stats
from hashlib import md5
from json import dumps
from logging import getLogger
from multiprocessing import Pool
from multiprocessing import cpu_count
from multiprocessing import get_start_method
from os import getpid
from os import kill
from os import makedirs
from os import unlink
from os.path import exists
from os.path import join
from pickle import HIGHEST_PROTOCOL
from pickle import dump
from pickle import load
from shutil import rmtree
from signal import SIGINT
from signal import SIGTERM
from signal import SIG_DFL
from signal import signal
from tempfile import NamedTemporaryFile
from tempfile import TemporaryDirectory
from tempfile import mkdtemp
from time import time
from typing import Any
from typing import cast

# Third party imports
# Third-party imports
import psutil

# Local imports
from marc_pd_tool.data.enums import MatchType
from marc_pd_tool.data.ground_truth import GroundTruthAnalysis
from marc_pd_tool.data.ground_truth import GroundTruthPair
from marc_pd_tool.data.ground_truth import GroundTruthStats
from marc_pd_tool.data.publication import Publication
from marc_pd_tool.exporters.json_exporter import save_matches_json
from marc_pd_tool.infrastructure.cache_manager import CacheManager
from marc_pd_tool.infrastructure.config_loader import get_config
from marc_pd_tool.loaders.copyright_loader import CopyrightDataLoader
from marc_pd_tool.loaders.marc_loader import MarcLoader
from marc_pd_tool.loaders.renewal_loader import RenewalDataLoader
from marc_pd_tool.processing.ground_truth_extractor import GroundTruthExtractor
from marc_pd_tool.processing.indexer import DataIndexer
from marc_pd_tool.processing.indexer import build_wordbased_index
from marc_pd_tool.processing.matching_engine import init_worker
from marc_pd_tool.processing.matching_engine import process_batch
from marc_pd_tool.processing.score_analyzer import ScoreAnalyzer
from marc_pd_tool.processing.text_processing import GenericTitleDetector
from marc_pd_tool.utils.time_utils import format_time_duration
from marc_pd_tool.utils.types import AnalysisOptions
from marc_pd_tool.utils.types import BatchProcessingInfo
from marc_pd_tool.utils.types import JSONDict
from marc_pd_tool.utils.types import JSONType
from marc_pd_tool.utils.types import MatchResultDict

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
        # Local imports
        from marc_pd_tool.exporters.json_exporter import save_matches_json

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
        # Local imports
        from marc_pd_tool.exporters.csv_exporter import CSVExporter

        exporter = CSVExporter(json_path, output_prefix)
        exporter.export()

        # Clean up temp file
        # Standard library imports

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
        # Local imports
        from marc_pd_tool.exporters.xlsx_exporter import XLSXExporter

        exporter = XLSXExporter(json_path, output_path)
        exporter.export()

        # Clean up temp file
        # Standard library imports

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
        # Local imports
        from marc_pd_tool.exporters.html_exporter import HTMLExporter

        exporter = HTMLExporter(json_path, output_dir)
        exporter.export()

        # Clean up temp file
        # Standard library imports

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


class MarcCopyrightAnalyzer:
    """High-level API for MARC copyright analysis

    This class provides a simplified interface for analyzing MARC records
    against copyright registration and renewal data. It handles data loading,
    indexing, matching, and result export.

    Example:
        >>> analyzer = MarcCopyrightAnalyzer()
        >>> analyzer.analyze_marc_file('data.marcxml', output_path='results.csv')
        >>> results = analyzer.get_results()
        >>> print(f"Found {results.statistics['pd_us_not_renewed']} public domain works")
    """

    def __init__(
        self,
        config_path: str | None = None,
        cache_dir: str | None = None,
        force_refresh: bool = False,
        log_file: str | None = None,
    ) -> None:
        """Initialize analyzer with configuration

        Args:
            config_path: Path to configuration JSON file
            cache_dir: Directory for caching indexes (default: .marcpd_cache)
            force_refresh: Force rebuild of cached indexes
            log_file: Path to log file (optional)
        """
        # Load configuration
        self.config = get_config(config_path) if config_path else get_config()

        # Initialize cache manager
        self.cache_dir = cache_dir or ".marcpd_cache"
        self.cache_manager = CacheManager(self.cache_dir)
        if force_refresh:
            logger.info("Force refresh requested - clearing all caches")
            self.cache_manager.clear_all_caches()

        # Initialize results container
        self.results = AnalysisResults()

        # Storage for loaded data and indexes
        self.copyright_data: list[Publication] | None = None
        self.renewal_data: list[Publication] | None = None
        self.registration_index: DataIndexer | None = None
        self.renewal_index: DataIndexer | None = None
        self.generic_detector: GenericTitleDetector | None = None

        # Default data directories
        self.copyright_dir = "nypl-reg/xml/"
        self.renewal_dir = "nypl-ren/data/"

        # Store analysis options for export metadata
        self.analysis_options: AnalysisOptions | None = None

    def analyze_marc_file(
        self,
        marc_path: str,
        copyright_dir: str | None = None,
        renewal_dir: str | None = None,
        output_path: str | None = None,
        options: AnalysisOptions | None = None,
    ) -> AnalysisResults:
        """Analyze a MARC XML file for copyright status

        Args:
            marc_path: Path to MARC XML file
            copyright_dir: Directory containing copyright XML files
            renewal_dir: Directory containing renewal TSV files
            output_path: Path for output file (optional)
            **options: Analysis options including:
                - us_only: Only analyze US publications
                - min_year: Minimum publication year
                - max_year: Maximum publication year
                - year_tolerance: Year matching tolerance (default: 1)
                - title_threshold: Title similarity threshold (default: 40)
                - author_threshold: Author similarity threshold (default: 30)
                - early_exit_title: Early exit title threshold (default: 95)
                - early_exit_author: Early exit author threshold (default: 90)
                - early_exit_publisher: Early exit publisher threshold (default: 85)
                - score_everything_mode: Find best match regardless of thresholds
                - minimum_combined_score: Minimum score for score_everything_mode mode
                - brute_force_missing_year: Process records without years
                - format: Output format ('csv', 'xlsx', 'json')
                - single_file: Export all results to single file

        Returns:
            AnalysisResults object containing processed publications and statistics
        """
        # Set data directories if provided
        if copyright_dir:
            self.copyright_dir = copyright_dir
        if renewal_dir:
            self.renewal_dir = renewal_dir

        # Initialize options if not provided
        if options is None:
            options = {}

        # Store options for later use
        self.analysis_options = options

        # Load and index copyright/renewal data
        self._load_and_index_data(options)

        # Load MARC records
        logger.info("=" * 80)
        logger.info("=== PHASE 2: LOADING MARC RECORDS ===")
        logger.info("=" * 80)
        logger.info(f"Loading MARC records from: {marc_path}")

        # Build parameters for MARC caching
        min_year = options.get("min_year")
        max_year = options.get("max_year")
        year_ranges = {"copyright": (min_year, max_year), "renewal": (min_year, max_year)}
        filtering_options: dict[str, bool | int] = {"us_only": bool(options.get("us_only", False))}
        if min_year is not None:
            filtering_options["min_year"] = min_year
        if max_year is not None:
            filtering_options["max_year"] = max_year

        # Check for cached MARC data
        cached_marc_batches = self.cache_manager.get_cached_marc_data(
            marc_path, year_ranges, filtering_options
        )

        if cached_marc_batches:
            marc_batches = cached_marc_batches
            marc_publications = [pub for batch in marc_batches for pub in batch]
            logger.info(f"✓ Loaded {len(marc_publications):,} MARC records from cache")
        else:
            # Load from files
            marc_loader = MarcLoader(
                marc_path=marc_path,
                batch_size=options.get("batch_size", 1000),
                min_year=min_year,
                max_year=max_year,
                us_only=options.get("us_only", False),
            )

            # Extract all batches and flatten
            marc_batches = marc_loader.extract_all_batches()
            marc_publications = [pub for batch in marc_batches for pub in batch]

            logger.info(f"✓ Loaded {len(marc_publications):,} MARC records")

            # Cache the loaded MARC data
            self.cache_manager.cache_marc_data(
                marc_path, year_ranges, filtering_options, marc_batches
            )

        # Log filtering information if applicable
        if options.get("us_only"):
            logger.info("  Filter applied: US publications only")
        if options.get("min_year") or options.get("max_year"):
            year_range = (
                f"{options.get('min_year') or 'earliest'} to {options.get('max_year') or 'present'}"
            )
            logger.info(f"  Year range filter: {year_range}")

        # Analyze publications
        self.analyze_marc_records(marc_publications, options)

        # Export results if output path provided
        if output_path:
            logger.info("")
            logger.info("=" * 80)
            logger.info("=== PHASE 5: EXPORTING RESULTS ===")
            logger.info("=" * 80)
            output_formats = options.get("formats", ["json", "csv"])
            single_file = options.get("single_file", False)
            logger.info(f"Exporting results to: {output_path}")
            logger.info(f"  Formats: {', '.join([f.upper() for f in output_formats])}")
            logger.info(
                f"  Single file: {'Yes' if single_file else 'No (separate files by status)'}"
            )
            self.export_results(output_path, formats=output_formats, single_file=single_file)
            logger.info("✓ Export complete")

        return self.results

    def analyze_marc_records(
        self, publications: list[Publication], options: AnalysisOptions | None = None
    ) -> list[Publication]:
        """Analyze a list of MARC publications

        Args:
            publications: List of Publication objects to analyze
            **options: Analysis options (see analyze_marc_file for details)

        Returns:
            List of analyzed Publication objects with copyright status
        """
        # Clear previous results
        self.results = AnalysisResults()

        # Initialize options if not provided
        if options is None:
            options = {}

        # Ensure data is loaded
        if not self.registration_index or not self.renewal_index:
            self._load_and_index_data(options)

        # Start matching
        logger.info("")
        logger.info("=" * 80)
        logger.info("=== PHASE 3: MATCHING RECORDS ===")
        logger.info("=" * 80)

        # Get processing parameters
        batch_size = options.get("batch_size", 200)
        num_processes = options.get("num_processes")
        if num_processes is None:
            num_processes = max(1, cpu_count() - 2)

        # Get matching parameters with defaults
        year_tolerance = options.get("year_tolerance", 1)
        title_threshold = options.get("title_threshold", 40)
        author_threshold = options.get("author_threshold", 30)
        publisher_threshold = options.get("publisher_threshold", 60)
        early_exit_title = options.get("early_exit_title", 95)
        early_exit_author = options.get("early_exit_author", 90)
        early_exit_publisher = options.get("early_exit_publisher", 85)
        score_everything_mode = options.get("score_everything_mode", False)
        minimum_combined_score_raw = options.get("minimum_combined_score", 40)
        minimum_combined_score = (
            int(cast(int | float, minimum_combined_score_raw)) if score_everything_mode else None
        )
        brute_force_missing_year = options.get("brute_force_missing_year", False)
        min_year = options.get("min_year")
        max_year = options.get("max_year")

        # Log matching configuration
        logger.info("Matching configuration:")
        logger.info(f"  Title threshold: {title_threshold}%")
        logger.info(f"  Author threshold: {author_threshold}%")
        logger.info(f"  Publisher threshold: {publisher_threshold}%")
        logger.info(f"  Year tolerance: ±{year_tolerance} years")
        logger.info(
            f"  Early exit thresholds: title={early_exit_title}%, author={early_exit_author}%, publisher={early_exit_publisher}%"
        )
        if score_everything_mode:
            logger.info(
                f"  Score everything mode: ON (minimum combined score: {minimum_combined_score}%)"
            )
        if brute_force_missing_year:
            logger.info("  Brute force mode: ON (processing records without years)")

        # Check if we should use multiprocessing
        if len(publications) < batch_size or num_processes == 1:
            # Process sequentially for small datasets
            logger.info("")
            logger.info(f"Processing {len(publications):,} records sequentially...")
            results = self._process_sequentially(
                publications,
                year_tolerance,
                title_threshold,
                author_threshold,
                publisher_threshold,
                early_exit_title,
                early_exit_author,
                early_exit_publisher,
                score_everything_mode,
                minimum_combined_score,
                brute_force_missing_year,
                min_year,
                max_year,
            )
        else:
            # Process in parallel for larger datasets
            logger.info("")
            logger.info(f"Processing {len(publications):,} records in parallel:")
            logger.info(f"  Workers: {num_processes}")
            logger.info(f"  Batch size: {batch_size}")
            logger.info(f"  Total batches: {(len(publications) + batch_size - 1) // batch_size}")
            results = self._process_parallel(
                publications,
                batch_size,
                num_processes,
                year_tolerance,
                title_threshold,
                author_threshold,
                publisher_threshold,
                early_exit_title,
                early_exit_author,
                early_exit_publisher,
                score_everything_mode,
                minimum_combined_score,
                brute_force_missing_year,
                min_year,
                max_year,
            )

        # Analyze copyright status
        logger.info("")
        logger.info("=" * 80)
        logger.info("=== PHASE 4: ANALYZING RESULTS ===")
        logger.info("=" * 80)
        logger.info("Determining copyright status for matched records...")

        # Log summary statistics
        stats = self.results.statistics
        logger.info(f"\u2713 Analysis complete:")
        logger.info(f"  Total records processed: {stats['total_records']:,}")
        if stats.get("skipped_no_year", 0) > 0:
            logger.info(f"  Records skipped (no year): {stats['skipped_no_year']:,}")
        logger.info(f"  Registration matches: {stats['registration_matches']:,}")
        logger.info(f"  Renewal matches: {stats['renewal_matches']:,}")
        logger.info(f"  No matches found: {stats['no_matches']:,}")

        return results

    def get_results(self) -> AnalysisResults:
        """Get analysis results

        Returns:
            AnalysisResults object with publications and statistics
        """
        return self.results

    def export_results(
        self, output_path: str, formats: list[str] | None = None, single_file: bool = False
    ) -> None:
        """Export results in specified formats (JSON always generated first)

        Args:
            output_path: Base path for output files (without extension)
            formats: List of output formats to generate. If None, defaults to ['json', 'csv']
            single_file: Export all results to single file (vs separated by status)

        Raises:
            ValueError: If format is not supported
        """
        # Default formats if not specified
        if formats is None:
            formats = ["json", "csv"]

        # Ensure JSON is always first
        if "json" not in formats:
            formats = ["json"] + formats
        elif formats[0] != "json":
            formats.remove("json")
            formats = ["json"] + formats

        # Load publications from disk if not already loaded
        if not self.results.publications and self.results.result_file_paths:
            logger.info("Loading publications from disk for export...")
            self.results.load_all_publications()

        # Always generate JSON first (master format)
        json_path = f"{output_path}.json"
        # Convert AnalysisOptions to dict for save_matches_json
        params: dict[str, str | int | float | bool] | None = None
        if self.analysis_options:
            # Convert AnalysisOptions TypedDict to regular dict with proper types
            params = {}
            for k, v in self.analysis_options.items():
                if v is not None:
                    # Ensure values are of expected types
                    if isinstance(v, (str, int, float, bool)):
                        params[k] = v
                    else:
                        # Convert to string for any other types
                        params[str(k)] = str(v)

        # JSON is always a single file regardless of single_file parameter
        # The single_file parameter only affects CSV and other formats
        save_matches_json(self.results.publications, json_path, parameters=params)
        logger.info(f"Generated JSON file: {json_path}")

        # Generate other requested formats from JSON
        for fmt in formats[1:]:  # Skip JSON since we already generated it
            if fmt == "csv":
                csv_path = f"{output_path}.csv"
                # Local imports
                from marc_pd_tool.exporters.csv_exporter import CSVExporter

                csv_exporter = CSVExporter(json_path, csv_path, single_file=single_file)
                csv_exporter.export()
                logger.info(f"Generated CSV file(s) from JSON")
            elif fmt == "xlsx":
                xlsx_path = f"{output_path}.xlsx"
                # Local imports
                from marc_pd_tool.exporters.xlsx_exporter import XLSXExporter

                xlsx_exporter = XLSXExporter(json_path, xlsx_path, single_file=single_file)
                xlsx_exporter.export()
                logger.info(f"Generated XLSX file: {xlsx_path}")
            elif fmt == "html":
                html_dir = f"{output_path}_html"
                # Local imports
                from marc_pd_tool.exporters.html_exporter import HTMLExporter

                html_exporter = HTMLExporter(json_path, html_dir, single_file=single_file)
                html_exporter.export()
                logger.info(f"Generated HTML output in: {html_dir}/")
            else:
                logger.warning(f"Unsupported format: {fmt}")

        # Clean up result directory after export
        if self.results.result_temp_dir and exists(self.results.result_temp_dir):
            rmtree(self.results.result_temp_dir)
            logger.debug(f"Cleaned up result directory: {self.results.result_temp_dir}")
            self.results.result_temp_dir = None
            self.results.result_file_paths = []

    def get_statistics(self) -> dict[str, int]:
        """Get analysis statistics

        Returns:
            Dictionary of statistics including counts by status and country
        """
        return self.results.statistics.copy()

    def _process_sequentially(
        self,
        publications: list[Publication],
        year_tolerance: int,
        title_threshold: int,
        author_threshold: int,
        publisher_threshold: int,
        early_exit_title: int,
        early_exit_author: int,
        early_exit_publisher: int,
        score_everything_mode: bool,
        minimum_combined_score: int | None,
        brute_force_missing_year: bool,
        min_year: int | None,
        max_year: int | None,
    ) -> list[Publication]:
        """Process publications sequentially using process_batch"""
        logger.info(f"Processing {len(publications)} records sequentially")

        # Get configuration for process_batch
        config_dict = self.config.get_config()
        config_hash = self._compute_config_hash(config_dict)

        # Get detector config
        detector_config_raw = config_dict.get("generic_title_detection", {})
        detector_config: dict[str, int | bool] = {}
        if isinstance(detector_config_raw, dict):
            for key, value in detector_config_raw.items():
                if isinstance(value, (int, bool)):
                    detector_config[key] = value

        # Year filtering options are already passed as parameters

        # Create a temporary directory for the batch file
        with TemporaryDirectory() as temp_dir:
            # Save the batch to a temporary file
            batch_path = join(temp_dir, "batch_001.pkl")
            with open(batch_path, "wb") as f:
                dump(publications, f, protocol=HIGHEST_PROTOCOL)

            # Create result temp dir
            result_temp_dir = join(temp_dir, "results")
            makedirs(result_temp_dir, exist_ok=True)

            # Create a single batch with all publications
            batch_info: BatchProcessingInfo = (
                1,  # batch_id
                batch_path,  # batch_path (path to pickled publications)
                self.cache_dir,  # cache_dir
                self.copyright_dir,  # copyright_dir
                self.renewal_dir,  # renewal_dir
                config_hash,  # config_hash
                detector_config,  # detector_config
                1,  # total_batches
                title_threshold,
                author_threshold,
                publisher_threshold,
                year_tolerance,
                early_exit_title,
                early_exit_author,
                early_exit_publisher,
                score_everything_mode,
                minimum_combined_score,
                brute_force_missing_year,
                min_year,
                max_year,
                result_temp_dir,  # result_temp_dir
            )

            # Process using the same logic as parallel processing
            batch_id, result_file_path, stats = process_batch(batch_info)

            # Load the results from the pickle file
            with open(result_file_path, "rb") as f:
                processed_publications = cast(list[Publication], load(f))

        # Update results
        for pub in processed_publications:
            if isinstance(pub, Publication):
                self.results.add_publication(pub)

        # Update skipped count
        if "skipped_no_year" in stats:
            self.results.statistics["skipped_no_year"] = stats["skipped_no_year"]

        logger.info(
            f"Sequential processing complete: {stats['registration_matches_found']} registration, "
            f"{stats['renewal_matches_found']} renewal matches"
        )

        return self.results.publications

    def _process_parallel(
        self,
        publications: list[Publication],
        batch_size: int,
        num_processes: int,
        year_tolerance: int,
        title_threshold: int,
        author_threshold: int,
        publisher_threshold: int,
        early_exit_title: int,
        early_exit_author: int,
        early_exit_publisher: int,
        score_everything_mode: bool,
        minimum_combined_score: int | None,
        brute_force_missing_year: bool,
        min_year: int | None,
        max_year: int | None,
    ) -> list[Publication]:
        """Process publications in parallel using multiple processes"""
        start_time = time()

        # Create batches and pickle them to reduce memory usage
        # Create temporary directories for batch files and results
        batch_temp_dir = mkdtemp(prefix="marc_batches_")
        result_temp_dir = mkdtemp(prefix="marc_results_")
        logger.info(f"Creating pickled batches in: {batch_temp_dir}")
        logger.info(f"Worker results will be saved to: {result_temp_dir}")

        # Ensure cleanup on exit - only clean batch dir, keep results
        def cleanup_batch_dir() -> None:
            if exists(batch_temp_dir):
                rmtree(batch_temp_dir)
                logger.debug(f"Cleaned up batch directory: {batch_temp_dir}")

        # Register cleanup for normal exit
        register(cleanup_batch_dir)

        # Register cleanup for signals (interrupt, terminate)
        def signal_cleanup(signum: int, frame: Any) -> None:  # type: ignore[explicit-any]
            logger.info(f"Received signal {signum}, cleaning up...")
            cleanup_batch_dir()
            # Re-raise the signal to allow normal termination
            signal(signum, SIG_DFL)
            kill(getpid(), signum)

        signal(SIGINT, signal_cleanup)  # Ctrl+C
        signal(SIGTERM, signal_cleanup)  # kill command

        # Create and pickle batches
        batch_paths = []
        total_batches = 0
        for i in range(0, len(publications), batch_size):
            batch = publications[i : i + batch_size]
            batch_path = join(batch_temp_dir, f"batch_{total_batches:05d}.pkl")

            with open(batch_path, "wb") as f:
                dump(batch, f, protocol=HIGHEST_PROTOCOL)

            batch_paths.append(batch_path)
            total_batches += 1

            # Free memory immediately
            del batch

        logger.info(f"Created {total_batches} pickled batches of ~{batch_size} records each")
        logger.debug(
            f"Freed {len(publications) * 1000 / 1024 / 1024:.1f}MB (estimate) of MARC data from RAM"
        )

        # Get configuration hash for cache validation
        config_dict = self.config.get_config()
        config_hash = self._compute_config_hash(config_dict)

        # Get detector config
        detector_config_raw = config_dict.get("generic_title_detection", {})
        detector_config: dict[str, int | bool] = {}
        if isinstance(detector_config_raw, dict):
            for key, value in detector_config_raw.items():
                if isinstance(value, (int, bool)):
                    detector_config[key] = value

        # Create batch info tuples with paths instead of data
        batch_infos = []
        for i, batch_path in enumerate(batch_paths):
            batch_info: BatchProcessingInfo = (
                i + 1,  # batch_id
                batch_path,  # batch_path (changed from marc_batch)
                self.cache_dir,  # cache_dir
                self.copyright_dir,  # copyright_dir
                self.renewal_dir,  # renewal_dir
                config_hash,  # config_hash
                detector_config,  # detector_config
                total_batches,  # total_batches
                title_threshold,
                author_threshold,
                publisher_threshold,
                year_tolerance,
                early_exit_title,
                early_exit_author,
                early_exit_publisher,
                score_everything_mode,
                minimum_combined_score,
                brute_force_missing_year,
                min_year,
                max_year,
                result_temp_dir,  # result_temp_dir for workers to save results
            )
            batch_infos.append(batch_info)

        # Process batches in parallel
        all_stats = []
        completed_batches = 0
        total_reg_matches = 0
        total_ren_matches = 0

        # Log multiprocessing configuration
        start_method = get_start_method()
        logger.info(f"Multiprocessing start method: {start_method}")

        try:
            # Use Pool for multiprocessing with maxtasksperchild to prevent memory leaks
            # Calculate optimal recycling frequency based on workload
            # Goal: Each worker recycles 2-3 times max during the full run
            batches_per_worker = total_batches // num_processes

            if batches_per_worker < 20:
                # Small job: no recycling needed
                tasks_per_child = None
                logger.info("Small job detected - worker recycling disabled")
            else:
                # Larger jobs: recycle 2-3 times per worker lifetime
                # But not too frequently (min 50) or too rarely (max 200)
                tasks_per_child = max(50, min(200, batches_per_worker // 3))
                logger.info(f"Worker recycling: every {tasks_per_child} batches")
                logger.info(
                    f"Each worker will process ~{batches_per_worker} batches total, recycling ~{batches_per_worker // tasks_per_child} times"
                )

            # Platform-specific handling for true memory sharing
            if start_method == "fork":
                # Linux: Load indexes in main process BEFORE forking
                logger.info("Linux detected: Loading indexes in main process for memory sharing...")
                # Local imports
                from marc_pd_tool.infrastructure.cache_manager import CacheManager
                from marc_pd_tool.processing.matching_engine import DataMatcher

                # Load indexes once in main process
                cache_manager = CacheManager(self.cache_dir)
                cached_indexes = cache_manager.get_cached_indexes(
                    self.copyright_dir,
                    self.renewal_dir,
                    config_hash,
                    min_year,
                    max_year,
                    brute_force_missing_year,
                )
                if cached_indexes is None:
                    raise RuntimeError("Failed to load indexes in main process")

                registration_index, renewal_index = cached_indexes
                logger.info(
                    f"Main process loaded {registration_index.size():,} registration, "
                    f"{renewal_index.size() if renewal_index else 0:,} renewal entries"
                )

                # Log memory usage after loading
                # Third party imports

                process = psutil.Process()
                mem_mb = process.memory_info().rss / 1024 / 1024
                logger.info(f"Main process memory after loading indexes: {mem_mb:.1f}MB")

                # Load generic detector
                generic_detector = cache_manager.get_cached_generic_detector(
                    self.copyright_dir, self.renewal_dir, detector_config
                )

                # Store in global for fork to inherit
                # Local imports
                from marc_pd_tool.processing import matching_engine as me

                me._shared_data = {
                    "registration_index": registration_index,
                    "renewal_index": renewal_index,
                    "generic_detector": generic_detector,
                    "matching_engine": DataMatcher(),
                }

                # Use minimal initializer that just sets up worker data from shared
                def init_worker_fork() -> None:
                    """Initialize worker on Linux - use pre-loaded shared data"""
                    # Standard library imports

                    me._worker_data = me._shared_data
                    logger.info(f"Worker {getpid()} using shared memory indexes")

                pool_args = {
                    "processes": num_processes,
                    "initializer": init_worker_fork,
                    "maxtasksperchild": tasks_per_child,
                }
            else:
                # macOS/Windows: Each worker loads independently
                logger.info("Spawn mode detected: Workers will load indexes independently")
                init_args = (
                    self.cache_dir,
                    self.copyright_dir,
                    self.renewal_dir,
                    config_hash,
                    detector_config,
                    min_year,
                    max_year,
                    brute_force_missing_year,
                )

                pool_args = {
                    "processes": num_processes,
                    "initializer": init_worker,
                    "initargs": init_args,
                    "maxtasksperchild": tasks_per_child,
                }

            # Create pool with platform-specific arguments
            with Pool(**pool_args) as pool:  # type: ignore[arg-type]
                logger.info(f"Processing {total_batches} batches with {num_processes} workers")

                # Process batches as they complete (unordered for efficiency)
                batch_submit_time = time()  # Track when we start submitting batches

                for batch_id_result, result_file_path, batch_stats in pool.imap_unordered(
                    process_batch, batch_infos, chunksize=1
                ):
                    try:
                        batch_complete_time = time()
                        batch_id = batch_id_result

                        # Load only statistics file - not the full publications
                        try:
                            # Construct stats file path from result file path
                            stats_file_path = result_file_path.replace("result_", "stats_")

                            # Load just the statistics (small data)
                            with open(stats_file_path, "rb") as stats_file:
                                detailed_stats: JSONType = load(stats_file)

                            # Update statistics directly
                            if isinstance(detailed_stats, dict):
                                for key, value in detailed_stats.items():
                                    if isinstance(key, str) and isinstance(value, int):
                                        if key in self.results.statistics:
                                            self.results.statistics[key] += value
                                        else:
                                            # For copyright status counts
                                            self.results.statistics[key] = (
                                                self.results.statistics.get(key, 0) + value
                                            )

                            # Track the result file path for later loading
                            self.results.add_result_file(result_file_path)

                            # Delete the stats file - we don't need it anymore
                            unlink(stats_file_path)

                            # Log tracking info (avoid using detailed_stats directly)
                            total_records = 0
                            if (
                                isinstance(detailed_stats, dict)
                                and "total_records" in detailed_stats
                            ):
                                tr = detailed_stats["total_records"]
                                if isinstance(tr, int):
                                    total_records = tr
                            logger.debug(
                                f"Tracked result file: {result_file_path} ({total_records} publications)"
                            )

                        except Exception as e:
                            logger.error(
                                f"Failed to process statistics from {result_file_path}: {e}"
                            )
                            # Continue processing other batches

                        # Track stats
                        all_stats.append(batch_stats)
                        completed_batches += 1

                        # Use actual processing time from worker
                        batch_duration = batch_stats[
                            "processing_time"
                        ]  # Use actual processing time
                        batch_duration_str = format_time_duration(batch_duration)

                        # Calculate overall progress and ETA
                        elapsed = batch_complete_time - start_time
                        eta = (elapsed / completed_batches) * (total_batches - completed_batches)
                        eta_str = format_time_duration(eta)

                        # Update totals
                        reg_matches = batch_stats["registration_matches_found"]
                        ren_matches = batch_stats["renewal_matches_found"]
                        total_reg_matches += reg_matches
                        total_ren_matches += ren_matches

                        # Log progress with all requested info
                        logger.info(
                            f"    Completed batch {batch_id}/{total_batches}: "
                            f"{reg_matches} reg, {ren_matches} ren | "
                            f"Set total: {total_reg_matches} registrations, {total_ren_matches} renewals"
                        )
                        logger.info(
                            f"    Batch time: {batch_duration_str} | "
                            f"Progress: {completed_batches}/{total_batches} | "
                            f"({completed_batches/total_batches*100:.1f}%) | "
                            f"ETA: {eta_str}"
                        )

                        # More frequent memory check for debugging
                        if completed_batches % 5 == 0:
                            process = psutil.Process()
                            mem_info = process.memory_info()
                            mem_mb = mem_info.rss / 1024 / 1024

                            # Get garbage collection stats
                            gc_stats = gc_get_stats()
                            gc0_collections = 0
                            if gc_stats and len(gc_stats) > 0:
                                first_stat = gc_stats[0]
                                if isinstance(first_stat, dict) and "collections" in first_stat:
                                    gc0_collections = first_stat["collections"]

                            logger.debug(
                                f"Memory after {completed_batches} batches: RSS={mem_mb:.1f}MB, "
                                f"GC Gen0 collections={gc0_collections}, "
                                f"Result files={len(self.results.result_file_paths)}, "
                                f"Stats entries={len(all_stats)}"
                            )

                    except Exception as e:
                        logger.error(f"Error processing batch {batch_id}: {e}")
                        logger.error(f"Error type: {type(e).__name__}")

                        # For timeout or other errors, create empty results for this batch
                        # This allows processing to continue with other batches
                        if "timeout" in str(e).lower() or type(e).__name__ == "TimeoutError":
                            logger.warning(
                                f"Batch {batch_id} timed out after 15 minutes - skipping"
                            )
                            # Create minimal stats for failed batch
                            failed_stats: dict[str, int] = {
                                "batch_id": batch_id,
                                "marc_count": 0,
                                "registration_matches_found": 0,
                                "renewal_matches_found": 0,
                                "total_comparisons": 0,
                                "us_records": 0,
                                "non_us_records": 0,
                                "unknown_country_records": 0,
                                "skipped_no_year": 0,
                            }
                            all_stats.append(failed_stats)  # type: ignore[arg-type]
                            completed_batches += 1
                            continue
                        else:
                            # For other errors, still try to continue
                            logger.error("Attempting to continue with remaining batches...")
                            continue

        except Exception as e:
            logger.error(f"Fatal error during parallel processing: {e}")
            raise
        finally:
            # Ensure batch directory is cleaned up even on error
            cleanup_batch_dir()
            # Unregister the atexit handler since we've already cleaned up
            unregister(cleanup_batch_dir)

        # Aggregate skipped_no_year counts from all batches
        total_skipped_no_year = sum(
            stats.get("skipped_no_year", 0) for stats in all_stats if isinstance(stats, dict)
        )
        self.results.statistics["skipped_no_year"] = total_skipped_no_year

        # Log final performance stats
        total_time = time() - start_time
        total_records = self.results.statistics["total_records"]
        records_per_minute = total_records / (total_time / 60) if total_time > 0 else 0

        logger.info(
            f"Parallel processing complete: {total_records} records in "
            f"{format_time_duration(total_time)} ({records_per_minute:.0f} records/minute)"
        )

        # Store result directory path for later cleanup
        self.results.result_temp_dir = result_temp_dir

        return self.results.publications

    def _load_and_index_data(self, options: AnalysisOptions) -> None:
        """Load and index copyright/renewal data"""
        logger.info("=" * 80)
        logger.info("=== PHASE 1: LOADING COPYRIGHT/RENEWAL DATA ===")
        logger.info("=" * 80)

        # Extract year filtering options
        min_year = options.get("min_year")
        max_year = options.get("max_year")
        brute_force = options.get("brute_force_missing_year", False)

        # Log the loading parameters
        if brute_force or (min_year is None and max_year is None):
            logger.info("Loading ALL years of copyright/renewal data")
        else:
            year_range = f"{min_year or 'earliest'} to {max_year or 'present'}"
            logger.info(f"Loading copyright/renewal data for years: {year_range}")

        # Check for cached indexes
        config_dict = self.config.get_config()
        config_hash = self._compute_config_hash(config_dict)

        cached_indexes = self.cache_manager.get_cached_indexes(
            self.copyright_dir, self.renewal_dir, config_hash, min_year, max_year, brute_force
        )

        if cached_indexes:
            self.registration_index, self.renewal_index = cached_indexes
            if brute_force or (min_year is None and max_year is None):
                logger.info("Loaded indexes from cache (ALL years)")
            else:
                logger.info(
                    f"Loaded indexes from cache (years {min_year or 'earliest'}-{max_year or 'present'})"
                )
        else:
            # Load copyright data
            logger.info(f"Loading copyright registration data from: {self.copyright_dir}")
            cached_copyright = self.cache_manager.get_cached_copyright_data(
                self.copyright_dir, min_year, max_year, brute_force
            )

            if cached_copyright:
                self.copyright_data = cached_copyright
            else:
                loader = CopyrightDataLoader(self.copyright_dir)
                self.copyright_data = loader.load_all_copyright_data(min_year, max_year)
                self.cache_manager.cache_copyright_data(
                    self.copyright_dir, self.copyright_data, min_year, max_year, brute_force
                )

            # Load renewal data
            logger.info(f"Loading copyright renewal data from: {self.renewal_dir}")
            cached_renewal = self.cache_manager.get_cached_renewal_data(
                self.renewal_dir, min_year, max_year, brute_force
            )

            if cached_renewal:
                self.renewal_data = cached_renewal
            else:
                renewal_loader = RenewalDataLoader(self.renewal_dir)
                self.renewal_data = renewal_loader.load_all_renewal_data(min_year, max_year)
                self.cache_manager.cache_renewal_data(
                    self.renewal_dir, self.renewal_data, min_year, max_year, brute_force
                )

            # Build indexes
            logger.info("Building word-based indexes for fast matching...")
            self.registration_index = build_wordbased_index(self.copyright_data, self.config)
            self.renewal_index = build_wordbased_index(self.renewal_data, self.config)
            logger.info(
                f"Built indexes: {len(self.registration_index.publications):,} registration, {len(self.renewal_index.publications):,} renewal entries"
            )

            # Cache indexes
            self.cache_manager.cache_indexes(
                self.copyright_dir,
                self.renewal_dir,
                config_hash,
                self.registration_index,
                self.renewal_index,
                min_year,
                max_year,
                brute_force,
            )

        # Initialize generic title detector
        detector_config_raw = config_dict.get("generic_title_detection", {})
        detector_config: dict[str, int | bool] = {}
        if isinstance(detector_config_raw, dict):
            for key, value in detector_config_raw.items():
                if isinstance(value, (int, bool)):
                    detector_config[key] = value
        if not detector_config.get("disabled", False):
            cached_detector = self.cache_manager.get_cached_generic_detector(
                self.copyright_dir, self.renewal_dir, detector_config
            )

            if cached_detector:
                self.generic_detector = cached_detector
            else:
                self.generic_detector = GenericTitleDetector(
                    frequency_threshold=int(detector_config.get("frequency_threshold", 10)),
                    config=self.config,
                )
                # Note: GenericTitleDetector tracks title frequencies automatically
                # as it processes titles during matching

                self.cache_manager.cache_generic_detector(
                    self.copyright_dir, self.renewal_dir, detector_config, self.generic_detector
                )

    def _apply_match_to_publication(
        self, pub: Publication, match_result: MatchResultDict, match_type: str
    ) -> None:
        """Apply match result to publication"""
        # Local imports
        from marc_pd_tool.data.publication import MatchResult
        from marc_pd_tool.processing.text_processing import extract_best_publisher_match

        match = MatchResult(
            matched_title=match_result["copyright_record"]["title"],
            matched_author=match_result["copyright_record"]["author"],
            similarity_score=match_result["similarity_scores"]["combined"],
            title_score=match_result["similarity_scores"]["title"],
            author_score=match_result["similarity_scores"]["author"],
            publisher_score=match_result["similarity_scores"]["publisher"],
            year_difference=(
                abs(pub.year - match_result["copyright_record"]["year"])
                if pub.year and match_result["copyright_record"]["year"]
                else 0
            ),
            source_id=match_result["copyright_record"]["source_id"],
            matched_publisher=(
                extract_best_publisher_match(
                    pub.original_publisher, match_result["copyright_record"]["full_text"]
                )
                if match_type == "renewal" and match_result["copyright_record"].get("full_text")
                else match_result["copyright_record"]["publisher"]
            ),
            source_type=match_type,
            matched_date=match_result["copyright_record"]["pub_date"],
            match_type=(
                MatchType.LCCN
                if match_result.get("is_lccn_match", False)
                else (
                    MatchType.BRUTE_FORCE_WITHOUT_YEAR if pub.year is None else MatchType.SIMILARITY
                )
            ),
        )

        if match_type == "registration":
            pub.set_registration_match(match)
        else:
            pub.set_renewal_match(match)

        # Handle generic title info
        if "generic_title_info" in match_result and match_result["generic_title_info"]:
            generic_info = match_result["generic_title_info"]
            if generic_info["has_generic_title"]:
                pub.generic_title_detected = True
                if match_type == "registration":
                    pub.registration_generic_title = True
                else:
                    pub.renewal_generic_title = True

                if generic_info["marc_title_is_generic"]:
                    pub.generic_detection_reason = generic_info["marc_detection_reason"]
                else:
                    pub.generic_detection_reason = generic_info["copyright_detection_reason"]

    def _compute_config_hash(self, config_dict: JSONDict) -> str:
        """Compute hash of configuration for cache validation"""
        # Standard library imports

        # Create a stable string representation
        config_str = dumps(config_dict, sort_keys=True)
        return md5(config_str.encode()).hexdigest()

    def extract_ground_truth(
        self,
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
        marc_batches = marc_loader.extract_all_batches()

        # Load copyright and renewal data if not already loaded
        if not self.copyright_data or not self.renewal_data:
            self._load_and_index_data({"min_year": min_year, "max_year": max_year})

        # Extract ground truth pairs
        extractor = GroundTruthExtractor()
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
        self, ground_truth_pairs: list[GroundTruthPair] | None = None
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
        self,
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

        analyzer = ScoreAnalyzer()

        # Always log the analysis report
        report = analyzer.generate_analysis_report(self.results.ground_truth_analysis)
        logger.info("\n" + report)

        # Export in all requested formats
        if self.results.ground_truth_pairs:
            # Convert GroundTruthPair objects to Publication list
            publications = []
            for pair in self.results.ground_truth_pairs:
                # The MARC record already has the match result populated
                publications.append(pair.marc_record)

            # Always save to JSON first (needed as source for other formats)
            json_path = f"{output_path}.json"
            if "json" in output_formats:
                save_matches_json(publications, json_path)
                logger.info(f"Generated ground truth JSON file: {json_path}")
            else:
                # Save temporarily for other exporters
                save_matches_json(publications, json_path)

            # Export each requested format
            for fmt in output_formats:
                if fmt == "csv":
                    # Local imports
                    from marc_pd_tool.exporters.csv_exporter import CSVExporter

                    csv_exporter = CSVExporter(json_path, f"{output_path}.csv", single_file=True)
                    csv_exporter.export()
                    logger.info(f"Generated ground truth CSV file: {output_path}.csv")
                elif fmt == "xlsx":
                    # Local imports
                    from marc_pd_tool.exporters.xlsx_exporter import XLSXExporter

                    xlsx_exporter = XLSXExporter(json_path, f"{output_path}.xlsx", single_file=True)
                    xlsx_exporter.export()
                    logger.info(f"Generated ground truth XLSX file: {output_path}.xlsx")
                elif fmt == "html":
                    # Local imports
                    from marc_pd_tool.exporters.html_exporter import HTMLExporter

                    html_exporter = HTMLExporter(json_path, f"{output_path}_html", single_file=True)
                    html_exporter.export()
                    logger.info(f"Generated ground truth HTML files in: {output_path}_html/")
                elif fmt == "json":
                    # Already handled above
                    pass
                else:
                    logger.warning(f"Unsupported ground truth format: {fmt}")

            # Clean up temporary JSON if it wasn't requested
            if "json" not in output_formats:
                # Standard library imports
                from os import unlink

                try:
                    unlink(json_path)
                except FileNotFoundError:
                    pass

    def _export_ground_truth_json(self, output_path: str) -> None:
        """Export ground truth analysis as JSON"""
        # Standard library imports

        if not self.results.ground_truth_analysis:
            return

        analysis = self.results.ground_truth_analysis

        data = {
            "statistics": {
                "total_pairs": analysis.total_pairs,
                "registration_pairs": analysis.registration_pairs,
                "renewal_pairs": analysis.renewal_pairs,
            },
            "score_distributions": {
                "title": {
                    "mean": analysis.title_distribution.mean_score,
                    "median": analysis.title_distribution.median_score,
                    "min": analysis.title_distribution.min_score,
                    "max": analysis.title_distribution.max_score,
                    "percentile_5": analysis.title_distribution.percentile_5,
                    "percentile_25": analysis.title_distribution.percentile_25,
                    "percentile_75": analysis.title_distribution.percentile_75,
                    "percentile_95": analysis.title_distribution.percentile_95,
                },
                "author": {
                    "mean": analysis.author_distribution.mean_score,
                    "median": analysis.author_distribution.median_score,
                    "min": analysis.author_distribution.min_score,
                    "max": analysis.author_distribution.max_score,
                    "percentile_5": analysis.author_distribution.percentile_5,
                    "percentile_25": analysis.author_distribution.percentile_25,
                    "percentile_75": analysis.author_distribution.percentile_75,
                    "percentile_95": analysis.author_distribution.percentile_95,
                },
                "publisher": {
                    "mean": analysis.publisher_distribution.mean_score,
                    "median": analysis.publisher_distribution.median_score,
                    "min": analysis.publisher_distribution.min_score,
                    "max": analysis.publisher_distribution.max_score,
                    "percentile_5": analysis.publisher_distribution.percentile_5,
                    "percentile_25": analysis.publisher_distribution.percentile_25,
                    "percentile_75": analysis.publisher_distribution.percentile_75,
                    "percentile_95": analysis.publisher_distribution.percentile_95,
                },
                "combined": {
                    "mean": analysis.combined_distribution.mean_score,
                    "median": analysis.combined_distribution.median_score,
                    "min": analysis.combined_distribution.min_score,
                    "max": analysis.combined_distribution.max_score,
                    "percentile_5": analysis.combined_distribution.percentile_5,
                    "percentile_25": analysis.combined_distribution.percentile_25,
                    "percentile_75": analysis.combined_distribution.percentile_75,
                    "percentile_95": analysis.combined_distribution.percentile_95,
                },
            },
        }

        with open(output_path, "w") as f:
            f.write(dumps(data, indent=2))

        logger.info(f"Exported ground truth analysis to {output_path}")
