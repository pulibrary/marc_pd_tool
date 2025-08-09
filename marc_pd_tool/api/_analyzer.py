# marc_pd_tool/api/_analyzer.py

"""Main analyzer class that combines all mixins"""

# Standard library imports
from hashlib import md5
from json import dumps
from logging import getLogger
from multiprocessing import cpu_count
from typing import cast

# Local imports
from marc_pd_tool.api._export import ExportMixin
from marc_pd_tool.api._ground_truth import GroundTruthMixin
from marc_pd_tool.api._processing import ProcessingMixin
from marc_pd_tool.api._results import AnalysisResults
from marc_pd_tool.api._streaming import StreamingMixin
from marc_pd_tool.data.enums import MatchType
from marc_pd_tool.data.publication import MatchResult
from marc_pd_tool.data.publication import Publication
from marc_pd_tool.infrastructure.cache_manager import CacheManager
from marc_pd_tool.infrastructure.config_loader import ConfigLoader
from marc_pd_tool.infrastructure.config_loader import get_config
from marc_pd_tool.loaders.copyright_loader import CopyrightDataLoader
from marc_pd_tool.loaders.marc_loader import MarcLoader
from marc_pd_tool.loaders.renewal_loader import RenewalDataLoader
from marc_pd_tool.processing.indexer import DataIndexer
from marc_pd_tool.processing.indexer import build_wordbased_index
from marc_pd_tool.processing.text_processing import GenericTitleDetector
from marc_pd_tool.processing.text_processing import extract_best_publisher_match
from marc_pd_tool.utils.types import AnalysisOptions
from marc_pd_tool.utils.types import JSONDict
from marc_pd_tool.utils.types import MatchResultDict

logger = getLogger(__name__)


class MarcCopyrightAnalyzer(ProcessingMixin, StreamingMixin, GroundTruthMixin, ExportMixin):
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
            from marc_pd_tool.loaders.copyright_loader import CopyrightDataLoader
            from marc_pd_tool.loaders.renewal_loader import RenewalDataLoader

            copyright_loader = CopyrightDataLoader(self.copyright_dir)
            renewal_loader = RenewalDataLoader(self.renewal_dir)

            max_copyright_year = copyright_loader.get_max_data_year()
            max_renewal_year = renewal_loader.get_max_data_year()

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
        marc_loader = MarcLoader(
            marc_path=marc_path,
            batch_size=options.get("batch_size", 1000),
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

        # Check for cached MARC data
        cached_marc_batches = self.cache_manager.get_cached_marc_data(
            marc_path, year_ranges, filtering_options
        )

        if cached_marc_batches:
            marc_batches = cached_marc_batches
            marc_publications = [pub for batch in marc_batches for pub in batch]
            logger.info(f"✓ Loaded {len(marc_publications):,} MARC records from cache")
        else:
            # Extract all batches (now always uses streaming internally)
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
        logger.info(f"✓ Analysis complete:")
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
        # Create a stable string representation
        config_str = dumps(config_dict, sort_keys=True)
        return md5(config_str.encode()).hexdigest()
