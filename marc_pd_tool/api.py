# marc_pd_tool/api.py

"""High-level API for MARC copyright analysis

This module provides the main public API for the marc_pd_tool package,
offering a simplified interface for analyzing MARC records against
copyright and renewal data.
"""

# Standard library imports
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures import as_completed
from logging import getLogger
from multiprocessing import cpu_count
from time import time
from typing import cast

# Local imports
from marc_pd_tool.data.enums import MatchType
from marc_pd_tool.data.ground_truth import GroundTruthAnalysis
from marc_pd_tool.data.ground_truth import GroundTruthPair
from marc_pd_tool.data.ground_truth import GroundTruthStats
from marc_pd_tool.data.publication import Publication
from marc_pd_tool.exporters import XLSXExporter
from marc_pd_tool.exporters.csv_exporter import save_matches_csv
from marc_pd_tool.exporters.json_exporter import save_matches_json
from marc_pd_tool.infrastructure.cache_manager import CacheManager
from marc_pd_tool.infrastructure.config_loader import get_config
from marc_pd_tool.loaders.copyright_loader import CopyrightDataLoader
from marc_pd_tool.loaders.marc_loader import MarcLoader
from marc_pd_tool.loaders.renewal_loader import RenewalDataLoader
from marc_pd_tool.processing.ground_truth_extractor import GroundTruthExtractor
from marc_pd_tool.processing.indexer import DataIndexer
from marc_pd_tool.processing.indexer import build_wordbased_index
from marc_pd_tool.processing.matching_engine import process_batch
from marc_pd_tool.processing.score_analyzer import ScoreAnalyzer
from marc_pd_tool.processing.text_processing import GenericTitleDetector
from marc_pd_tool.utils.time_utils import format_time_duration
from marc_pd_tool.utils.types import AnalysisOptions
from marc_pd_tool.utils.types import BatchProcessingInfo
from marc_pd_tool.utils.types import JSONDict
from marc_pd_tool.utils.types import MatchResultDict

logger = getLogger(__name__)


class AnalysisResults:
    """Container for analysis results with statistics and export capabilities"""

    def __init__(self) -> None:
        """Initialize empty results container"""
        self.publications: list[Publication] = []
        self.statistics: dict[str, int] = {
            "total_records": 0,
            "us_records": 0,
            "non_us_records": 0,
            "unknown_country": 0,
            "registration_matches": 0,
            "renewal_matches": 0,
            "pd_no_renewal": 0,
            "pd_date_verify": 0,
            "in_copyright": 0,
            "research_us_status": 0,
            "research_us_only_pd": 0,
            "country_unknown": 0,
        }
        self.ground_truth_analysis: GroundTruthAnalysis | None = None
        self.ground_truth_pairs: list[GroundTruthPair] | None = None
        self.ground_truth_stats: GroundTruthStats | None = None

    def add_publication(self, pub: Publication) -> None:
        """Add a publication to results and update statistics"""
        self.publications.append(pub)
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
        if pub.has_registration_match():
            self.statistics["registration_matches"] += 1
        if pub.has_renewal_match():
            self.statistics["renewal_matches"] += 1

        # Copyright status
        if hasattr(pub, "copyright_status") and pub.copyright_status:
            status_key = pub.copyright_status.value.lower()
            if status_key in self.statistics:
                self.statistics[status_key] += 1


class MarcCopyrightAnalyzer:
    """High-level API for MARC copyright analysis

    This class provides a simplified interface for analyzing MARC records
    against copyright registration and renewal data. It handles data loading,
    indexing, matching, and result export.

    Example:
        >>> analyzer = MarcCopyrightAnalyzer()
        >>> analyzer.analyze_marc_file('data.marcxml', output_path='results.csv')
        >>> results = analyzer.get_results()
        >>> print(f"Found {results.statistics['pd_no_renewal']} public domain works")
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

        # Load and index copyright/renewal data
        self._load_and_index_data(options)

        # Load MARC records
        logger.info(f"Loading MARC records from {marc_path}")
        marc_loader = MarcLoader(
            marc_path=marc_path,
            batch_size=options.get("batch_size", 1000),
            min_year=options.get("min_year"),
            max_year=options.get("max_year"),
            us_only=options.get("us_only", False),
        )

        # Extract all batches and flatten
        marc_batches = marc_loader.extract_all_batches()
        marc_publications = [pub for batch in marc_batches for pub in batch]

        logger.info(f"Loaded {len(marc_publications)} MARC records")

        # Analyze publications
        self.analyze_marc_records(marc_publications, options)

        # Export results if output path provided
        if output_path:
            output_format = options.get("format", "csv")
            single_file = options.get("single_file", False)
            self.export_results(output_path, format=output_format, single_file=single_file)

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
        score_everything_mode = options.get("score_everything_mode", False)
        minimum_combined_score_raw = options.get("minimum_combined_score", 40)
        minimum_combined_score = (
            int(cast(int | float, minimum_combined_score_raw)) if score_everything_mode else None
        )
        brute_force_missing_year = options.get("brute_force_missing_year", False)

        # Check if we should use multiprocessing
        if len(publications) < batch_size or num_processes == 1:
            # Process sequentially for small datasets
            logger.info("Processing sequentially due to small dataset or single process requested")
            return self._process_sequentially(
                publications,
                year_tolerance,
                title_threshold,
                author_threshold,
                publisher_threshold,
                early_exit_title,
                early_exit_author,
                score_everything_mode,
                minimum_combined_score,
                brute_force_missing_year,
            )

        # Process in parallel for larger datasets
        logger.info(
            f"Processing {len(publications)} records in parallel with {num_processes} workers"
        )
        return self._process_parallel(
            publications,
            batch_size,
            num_processes,
            year_tolerance,
            title_threshold,
            author_threshold,
            publisher_threshold,
            early_exit_title,
            early_exit_author,
            score_everything_mode,
            minimum_combined_score,
            brute_force_missing_year,
        )

    def get_results(self) -> AnalysisResults:
        """Get analysis results

        Returns:
            AnalysisResults object with publications and statistics
        """
        return self.results

    def export_results(
        self, output_path: str, format: str = "csv", single_file: bool = False
    ) -> None:
        """Export results in specified format

        Args:
            output_path: Path for output file
            format: Output format ('csv', 'xlsx', 'json')
            single_file: Export all results to single file (vs separated by status)

        Raises:
            ValueError: If format is not supported
        """
        if format == "csv":
            save_matches_csv(self.results.publications, output_path, single_file=single_file)
        elif format == "xlsx":
            exporter = XLSXExporter(
                self.results.publications, output_path, score_everything_mode=single_file
            )
            exporter.export()
        elif format == "json":
            save_matches_json(self.results.publications, output_path)
        else:
            raise ValueError(f"Unsupported format: {format}")

        logger.info(f"Results exported to {output_path}")

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
        score_everything_mode: bool,
        minimum_combined_score: int | None,
        brute_force_missing_year: bool,
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

        # Create a single batch with all publications
        batch_info: BatchProcessingInfo = (
            1,  # batch_id
            publications,  # marc_batch
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
            score_everything_mode,
            minimum_combined_score,
            brute_force_missing_year,
        )

        # Process using the same logic as parallel processing
        _, processed_publications, stats = process_batch(batch_info)

        # Update results
        for pub in processed_publications:
            self.results.add_publication(pub)

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
        score_everything_mode: bool,
        minimum_combined_score: int | None,
        brute_force_missing_year: bool,
    ) -> list[Publication]:
        """Process publications in parallel using multiple processes"""
        start_time = time()

        # Create batches
        batches = []
        for i in range(0, len(publications), batch_size):
            batch = publications[i : i + batch_size]
            batches.append(batch)

        total_batches = len(batches)
        logger.info(f"Created {total_batches} batches of ~{batch_size} records each")

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

        # Create batch info tuples
        batch_infos = []
        for i, batch in enumerate(batches):
            batch_info: BatchProcessingInfo = (
                i + 1,  # batch_id
                batch,  # marc_batch
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
                score_everything_mode,
                minimum_combined_score,
                brute_force_missing_year,
            )
            batch_infos.append(batch_info)

        # Process batches in parallel
        all_processed_publications = []
        all_stats = []
        completed_batches = 0
        total_reg_matches = 0
        total_ren_matches = 0
        batch_start_times = {}  # Track when each batch started

        try:
            with ProcessPoolExecutor(max_workers=num_processes) as executor:
                # Submit all jobs
                future_to_batch = {}
                for batch_info in batch_infos:
                    batch_id = batch_info[0]
                    future = executor.submit(process_batch, batch_info)
                    future_to_batch[future] = batch_id
                    batch_start_times[batch_id] = time()  # Record submission time

                logger.info(
                    f"Submitted {total_batches} batches for processing with {num_processes} workers"
                )

                # Collect results as they complete
                for future in as_completed(future_to_batch):
                    batch_id = future_to_batch[future]
                    batch_complete_time = time()

                    try:
                        batch_id_result, processed_batch, batch_stats = future.result()
                        all_processed_publications.extend(processed_batch)
                        all_stats.append(batch_stats)
                        completed_batches += 1

                        # Calculate batch duration
                        batch_duration = batch_complete_time - batch_start_times[batch_id]
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
                            f"Completed batch {batch_id}/{total_batches}: "
                            f"{reg_matches} new registration, {ren_matches} new renewal matches | "
                            f"Total: {total_reg_matches} reg, {total_ren_matches} ren | "
                            f"Batch time: {batch_duration_str} | "
                            f"Progress: {completed_batches}/{total_batches} "
                            f"({completed_batches/total_batches*100:.1f}%) | "
                            f"ETA: {eta_str}"
                        )

                    except Exception as e:
                        logger.error(f"Error processing batch {batch_id}: {e}")
                        raise

        except Exception as e:
            logger.error(f"Fatal error during parallel processing: {e}")
            raise

        # Update results with all processed publications
        for pub in all_processed_publications:
            self.results.add_publication(pub)

        # Log final performance stats
        total_time = time() - start_time
        total_records = len(all_processed_publications)
        records_per_minute = total_records / (total_time / 60) if total_time > 0 else 0

        logger.info(
            f"Parallel processing complete: {total_records} records in "
            f"{format_time_duration(total_time)} ({records_per_minute:.0f} records/minute)"
        )

        return self.results.publications

    def _load_and_index_data(self, options: AnalysisOptions) -> None:
        """Load and index copyright/renewal data"""
        # Extract year filtering options
        min_year = options.get("min_year")
        max_year = options.get("max_year")
        brute_force = options.get("brute_force_missing_year", False)

        # Check for cached indexes
        config_dict = self.config.get_config()
        config_hash = self._compute_config_hash(config_dict)

        cached_indexes = self.cache_manager.get_cached_indexes(
            self.copyright_dir, self.renewal_dir, config_hash
        )

        if cached_indexes:
            self.registration_index, self.renewal_index = cached_indexes
            logger.info("Loaded indexes from cache")
        else:
            # Load copyright data
            logger.info(f"Loading copyright data from {self.copyright_dir}")
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
            logger.info(f"Loading renewal data from {self.renewal_dir}")
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
            logger.info("Building word-based indexes")
            self.registration_index = build_wordbased_index(self.copyright_data, self.config)
            self.renewal_index = build_wordbased_index(self.renewal_data, self.config)

            # Cache indexes
            self.cache_manager.cache_indexes(
                self.copyright_dir,
                self.renewal_dir,
                config_hash,
                self.registration_index,
                self.renewal_index,
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
        from hashlib import md5
        from json import dumps

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

    def export_ground_truth_analysis(self, output_path: str, output_format: str = "csv") -> None:
        """Export ground truth analysis results

        Args:
            output_path: Path for output file
            output_format: Output format ('csv', 'xlsx', 'json')
        """
        if not self.results.ground_truth_analysis:
            raise ValueError("No ground truth analysis available to export")

        analyzer = ScoreAnalyzer()

        # Always log the analysis report
        report = analyzer.generate_analysis_report(self.results.ground_truth_analysis)
        logger.info("\n" + report)

        # Export based on format
        if output_format in ("csv", "xlsx"):
            # Use standard exporters for ground truth pairs
            if self.results.ground_truth_pairs:
                # Convert GroundTruthPair objects to Publication list
                publications = []
                for pair in self.results.ground_truth_pairs:
                    # The MARC record already has the match result populated
                    publications.append(pair.marc_record)

                # Use standard export methods
                if output_format == "csv":
                    save_matches_csv(publications, output_path, single_file=True)
                else:  # xlsx
                    exporter = XLSXExporter(publications, output_path)
                    exporter.export()

        elif output_format == "json":
            # Export full analysis as JSON
            self._export_ground_truth_json(output_path)
        else:
            raise ValueError(f"Unsupported output format: {output_format}")

    def _export_ground_truth_json(self, output_path: str) -> None:
        """Export ground truth analysis as JSON"""
        # Standard library imports
        from json import dumps

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
