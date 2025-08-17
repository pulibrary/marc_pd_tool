# marc_pd_tool/adapters/api/_analyzer.py

"""Main analyzer class that combines all mixins"""

# Standard library imports
from hashlib import md5
from json import dumps
from logging import getLogger
from typing import cast

# Local imports
from marc_pd_tool.adapters.api._export import ExportComponent
from marc_pd_tool.adapters.api._ground_truth import GroundTruthComponent
from marc_pd_tool.adapters.api._processing import ProcessingComponent
from marc_pd_tool.adapters.api._streaming import StreamingComponent
from marc_pd_tool.application.models.analysis_results import AnalysisResults
from marc_pd_tool.application.models.config_models import AnalysisOptions
from marc_pd_tool.application.processing.indexer import DataIndexer
from marc_pd_tool.application.processing.indexer import build_wordbased_index
from marc_pd_tool.application.processing.text_processing import (
    extract_best_publisher_match,
)
from marc_pd_tool.application.processing.text_processing import GenericTitleDetector
from marc_pd_tool.core.domain.enums import MatchType
from marc_pd_tool.core.domain.match_result import MatchResult
from marc_pd_tool.core.domain.publication import Publication
from marc_pd_tool.core.types.json import JSONDict
from marc_pd_tool.core.types.results import MatchResultDict
from marc_pd_tool.infrastructure import CacheManager
from marc_pd_tool.infrastructure.config import ConfigLoader
from marc_pd_tool.infrastructure.config import get_config
from marc_pd_tool.infrastructure.persistence import CopyrightDataLoader
from marc_pd_tool.infrastructure.persistence import MarcLoader
from marc_pd_tool.infrastructure.persistence import RenewalDataLoader

logger = getLogger(__name__)


class MarcCopyrightAnalyzer(
    ProcessingComponent, StreamingComponent, GroundTruthComponent, ExportComponent
):
    """High-level analyzer for MARC copyright status

    This class combines functionality from multiple mixins to provide
    a complete analysis pipeline for determining copyright status of
    MARC bibliographic records.
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
        self.config: ConfigLoader = get_config(config_path) if config_path else get_config()

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
        temp_dir: str | None = None,
    ) -> AnalysisResults:
        """Analyze a MARC XML file for copyright status

        Args:
            marc_path: Path to MARC XML file
            copyright_dir: Directory containing copyright XML files
            renewal_dir: Directory containing renewal TSV files
            output_path: Path for output file (optional)
            options: Analysis options including:
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
                - formats: Output formats ('csv', 'xlsx', 'json')
                - single_file: Export all results to single file
                - batch_size: Number of records per batch
                - num_processes: Number of worker processes
            temp_dir: Directory for temporary batch files (optional)

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

        # Load and index copyright/renewal data first
        self._load_and_index_data(options)

        # Dynamically determine the maximum year we have data for
        max_data_year = None
        try:
            # Local imports
            from marc_pd_tool.infrastructure.persistence import CopyrightDataLoader
            from marc_pd_tool.infrastructure.persistence import RenewalDataLoader

            copyright_loader = CopyrightDataLoader(self.copyright_dir)
            renewal_loader = RenewalDataLoader(self.renewal_dir)

            max_copyright_year = copyright_loader.max_data_year
            max_renewal_year = renewal_loader.max_data_year

            # Use the maximum of both (could be None if directories don't exist)
            if max_copyright_year is not None and max_renewal_year is not None:
                max_data_year = max(max_copyright_year, max_renewal_year)
            elif max_copyright_year is not None:
                max_data_year = max_copyright_year
            elif max_renewal_year is not None:
                max_data_year = max_renewal_year

            if max_data_year:
                logger.info(f"Maximum data year detected: {max_data_year}")
                logger.info(f"Records beyond {max_data_year} will be automatically filtered")
        except Exception as e:
            logger.warning(f"Could not determine max data year: {e}")

        # Create MARC loader with max_data_year
        # Use batch_size from options, which defaults to config.json value
        batch_size = options.get("batch_size", self.config.processing.batch_size)
        marc_loader = MarcLoader(
            marc_path=marc_path,
            batch_size=batch_size,
            min_year=options.get("min_year"),
            max_year=options.get("max_year"),
            us_only=options.get("us_only", False),
            max_data_year=max_data_year,
        )

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

        # Always use disk-based batch processing for memory efficiency
        # Extract MARC records to pickled batch files
        batch_paths, total_records, filtered_count = marc_loader.extract_batches_to_disk(temp_dir)

        if not batch_paths:
            logger.warning("No MARC records found or all records were filtered")
            return self.results

        logger.info(f"✓ Extracted {total_records:,} MARC records into {len(batch_paths)} batches")
        if filtered_count > 0:
            logger.info(f"  Filtered out {filtered_count:,} records")

        # Log filtering information if applicable
        if options.get("us_only"):
            logger.info("  Filter applied: US publications only")
        if options.get("min_year") or options.get("max_year"):
            year_range = (
                f"{options.get('min_year') or 'earliest'} to {options.get('max_year') or 'present'}"
            )
            logger.info(f"  Year range filter: {year_range}")

        # Process batches using efficient streaming approach
        self._process_marc_batches(batch_paths, marc_path, options)

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

            # Clean up temporary files after successful export
            if hasattr(self.results, "cleanup_temp_files"):
                self.results.cleanup_temp_files()

        return self.results

    def _process_marc_batches(
        self, batch_paths: list[str], marc_path: str, options: AnalysisOptions
    ) -> None:
        """Process MARC batches efficiently using streaming approach

        Args:
            batch_paths: List of paths to pickled batch files
            marc_path: Original MARC file path (for logging)
            options: Analysis options
        """
        # Use the streaming component's method directly
        self._analyze_marc_file_streaming(batch_paths, marc_path, None, options)

    def analyze_marc_records(
        self, publications: list[Publication], options: AnalysisOptions | None = None
    ) -> list[Publication]:
        """Analyze a list of MARC publications

        Args:
            publications: List of Publication objects to analyze
            options: Analysis options (see analyze_marc_file for details)

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
        # Use same batch_size default as loading phase
        batch_size = options.get("batch_size", self.config.processing.batch_size)
        num_processes = options.get("num_processes")
        # This should always be set by the CLI, but have a fallback just in case
        if num_processes is None:
            # Standard library imports
            from multiprocessing import cpu_count

            num_processes = max(1, cpu_count() - 4)

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
        options.get("min_year")
        options.get("max_year")

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

        # Create temporary batch files from publications list
        # Standard library imports
        from os.path import join
        from pickle import HIGHEST_PROTOCOL
        from pickle import dump
        from tempfile import mkdtemp

        temp_dir = mkdtemp(prefix="marc_analyze_")
        batch_paths = []

        # Split publications into batches and pickle them
        for i in range(0, len(publications), batch_size):
            batch = publications[i : i + batch_size]
            batch_id = len(batch_paths)
            batch_path = join(temp_dir, f"batch_{batch_id:05d}.pkl")
            with open(batch_path, "wb") as f:
                dump(batch, f, protocol=HIGHEST_PROTOCOL)
            batch_paths.append(batch_path)

        logger.info("")
        logger.info(f"Processing {len(publications):,} records in {len(batch_paths)} batch(es)...")
        if num_processes > 1:
            logger.info(f"  Workers: {num_processes}")
            logger.info(f"  Batch size: {batch_size}")

        # Process using the streaming approach
        self._analyze_marc_file_streaming(batch_paths, "in-memory", None, options)

        # Return the publications from results (for backward compatibility)
        results = self.results.publications

        # Analyze copyright status
        logger.info("")
        logger.info("=" * 80)
        logger.info("=== PHASE 4: ANALYZING RESULTS ===")
        logger.info("=" * 80)
        logger.info("Determining copyright status for matched records...")

        # Log summary statistics
        stats = self.results.statistics
        logger.info(f"✓ Analysis complete:")
        logger.info(f"  Total records processed: {stats.total_records:,}")
        if stats.skipped_no_year > 0:
            logger.info(f"  Records skipped (no year): {stats.skipped_no_year:,}")
        logger.info(f"  Registration matches: {stats.registration_matches:,}")
        logger.info(f"  Renewal matches: {stats.renewal_matches:,}")
        logger.info(f"  No matches found: {stats.no_matches:,}")

        return results

    def get_results(self) -> AnalysisResults:
        """Get analysis results

        Returns:
            AnalysisResults object with all processed publications and statistics
        """
        return self.results

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
        config_dict = self.config.config
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
                # Always use parallel loading (with automatic fallback to sequential if needed)
                num_workers = options.get("num_processes")  # Will be None if not specified
                loader = CopyrightDataLoader(self.copyright_dir, num_workers=num_workers)
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
                # Always use parallel loading (with automatic fallback to sequential if needed)
                num_workers = options.get("num_processes")  # Will be None if not specified
                renewal_loader = RenewalDataLoader(self.renewal_dir, num_workers=num_workers)
                self.renewal_data = renewal_loader.load_all_renewal_data(min_year, max_year)
                self.cache_manager.cache_renewal_data(
                    self.renewal_dir, self.renewal_data, min_year, max_year, brute_force
                )

            # Build indexes
            logger.info("Building word-based indexes for fast matching...")

            # Always try parallel index building first (with automatic fallback to sequential)
            try:
                # Local imports
                from marc_pd_tool.application.processing.parallel_indexer import (
                    build_wordbased_index_parallel,
                )

                num_workers = options.get("num_processes")  # Will be None if not specified
                self.registration_index = build_wordbased_index_parallel(
                    self.copyright_data, self.config, num_workers=num_workers
                )
                self.renewal_index = build_wordbased_index_parallel(
                    self.renewal_data, self.config, num_workers=num_workers
                )
            except Exception as e:
                logger.warning(f"Parallel index building failed, falling back to sequential: {e}")
                # Fall back to sequential index building
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
        detector_config: dict[str, int | bool] = {
            "frequency_threshold": self.config.generic_detector.frequency_threshold,
            "disable_generic_detection": self.config.generic_detector.disable_generic_detection,
        }
        if not detector_config.get("disable_generic_detection", False):
            cached_detector = self.cache_manager.get_cached_generic_detector(
                self.copyright_dir, self.renewal_dir, detector_config
            )

            if cached_detector:
                self.generic_detector = cached_detector
            else:
                self.generic_detector = GenericTitleDetector(
                    frequency_threshold=detector_config.get("frequency_threshold", 10),
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
            pub.registration_match = match
        else:
            pub.renewal_match = match

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
        # Create a stable string representation
        config_str = dumps(config_dict, sort_keys=True)
        return md5(config_str.encode()).hexdigest()
