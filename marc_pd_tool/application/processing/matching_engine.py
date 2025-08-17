# marc_pd_tool/application/processing/matching_engine.py

"""Data matching engine for comparing MARC records against copyright/renewal data

This is now a slim wrapper around the modular matching components.
"""

# Standard library imports
from logging import Formatter
from logging import INFO
from logging import StreamHandler
from logging import getLogger
from os import getpid
from os import unlink
from os.path import join
from pickle import HIGHEST_PROTOCOL
from pickle import dump
from pickle import load
from time import time

# Third party imports
import psutil

# Local imports
from marc_pd_tool.application.models.batch_stats import BatchStats
from marc_pd_tool.application.processing.matching._core_matcher import CoreMatcher
from marc_pd_tool.application.processing.similarity_calculator import (
    SimilarityCalculator,
)
from marc_pd_tool.application.processing.text_processing import GenericTitleDetector
from marc_pd_tool.core.domain.enums import MatchType
from marc_pd_tool.core.domain.match_result import MatchResult
from marc_pd_tool.core.domain.publication import Publication
from marc_pd_tool.core.types.aliases import BatchProcessingInfo
from marc_pd_tool.core.types.results import MatchResultDict
from marc_pd_tool.infrastructure.config import ConfigLoader

# Module logger - will be reconfigured in worker processes
logger = getLogger(__name__)


class DataMatcher:
    """Data matching engine - wrapper around CoreMatcher for compatibility"""

    def __init__(
        self,
        similarity_calculator: SimilarityCalculator | None = None,
        config: ConfigLoader | None = None,
    ):
        """Initialize with optional custom components and configuration

        Args:
            similarity_calculator: Custom similarity calculator
            config: Configuration loader, uses default if None
        """
        # Use the new CoreMatcher internally
        self.core_matcher = CoreMatcher(config=config, similarity_calculator=similarity_calculator)
        self.config = self.core_matcher.config
        self.similarity_calculator = self.core_matcher.similarity_calculator

    def find_best_match(
        self,
        marc_pub: Publication,
        copyright_pubs: list[Publication],
        title_threshold: int,
        author_threshold: int,
        publisher_threshold: int | None = None,
        year_tolerance: int = 1,
        early_exit_title: int = 95,
        early_exit_author: int = 90,
        early_exit_publisher: int | None = None,
        generic_detector: GenericTitleDetector | None = None,
    ) -> MatchResultDict | None:
        """Find best matching copyright/renewal record

        Delegates to CoreMatcher.
        """
        # Set generic detector if provided
        if generic_detector:
            self.core_matcher.generic_detector = generic_detector

        return self.core_matcher.find_best_match(
            marc_pub=marc_pub,
            copyright_pubs=copyright_pubs,
            title_threshold=title_threshold,
            author_threshold=author_threshold,
            publisher_threshold=publisher_threshold,
            year_tolerance=year_tolerance,
            early_exit_title=early_exit_title,
            early_exit_author=early_exit_author,
            early_exit_publisher=early_exit_publisher,
        )

    def find_best_match_ignore_thresholds(
        self,
        marc_pub: Publication,
        copyright_pubs: list[Publication],
        year_tolerance: int = 1,
        minimum_combined_score: int | None = None,
        generic_detector: GenericTitleDetector | None = None,
    ) -> MatchResultDict | None:
        """Find best match ignoring individual thresholds

        Delegates to CoreMatcher.
        """
        # Set generic detector if provided
        if generic_detector:
            self.core_matcher.generic_detector = generic_detector

        return self.core_matcher.find_best_match_ignore_thresholds(
            marc_pub=marc_pub,
            copyright_pubs=copyright_pubs,
            year_tolerance=year_tolerance,
            minimum_combined_score=minimum_combined_score,
        )


# Global variables for worker processes
_worker_registration_index = None
_worker_renewal_index = None
_worker_generic_detector = None
_worker_config = None
_worker_options: dict[str, object] | None = None


def init_worker(
    cache_dir: str,
    copyright_dir: str,
    renewal_dir: str,
    config_hash: str,
    detector_config: dict[str, int | bool],
    min_year: int | None,
    max_year: int | None,
    brute_force: bool,
) -> None:
    """Initialize worker process with pre-loaded indexes and components

    This function is called once per worker process to load the shared indexes.
    """
    global _worker_registration_index
    global _worker_renewal_index
    global _worker_generic_detector
    global _worker_config
    global _worker_options

    # Import here to avoid circular dependency
    # Local imports
    from marc_pd_tool.infrastructure import CacheManager

    # Load indexes from cache
    cache_manager = CacheManager(cache_dir)
    cached_indexes = cache_manager.get_cached_indexes(
        copyright_dir, renewal_dir, config_hash, min_year, max_year, brute_force
    )

    if cached_indexes is None:
        raise RuntimeError(f"Worker {getpid()}: Failed to load indexes from cache")

    _worker_registration_index, _worker_renewal_index = cached_indexes

    # Load generic detector
    _worker_generic_detector = cache_manager.get_cached_generic_detector(
        copyright_dir, renewal_dir, detector_config
    )

    # Load config
    # Local imports
    from marc_pd_tool.infrastructure.config import get_config

    _worker_config = get_config()

    # Store options - these will be passed in process_batch now
    _worker_options = {}

    # Configure logging for worker - use same format as main process but with worker ID
    worker_logger = getLogger()
    worker_logger.handlers.clear()
    handler = StreamHandler()
    # Match main process format but add Worker ID
    handler.setFormatter(Formatter("%(asctime)s - %(levelname)s - [Worker] %(message)s"))
    worker_logger.addHandler(handler)
    worker_logger.setLevel(INFO)

    # Also configure the module logger to use the same format
    global logger
    logger = getLogger(__name__)
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.setLevel(INFO)
    logger.propagate = False  # Don't propagate to root to avoid duplicates


def process_batch(batch_info: BatchProcessingInfo) -> tuple[int, str, BatchStats]:
    """Process a batch of MARC publications

    This function is called by worker processes to process batches.
    """
    # Unpack all the batch info
    (
        batch_id,
        batch_path,
        worker_cache_dir,
        copyright_dir,
        renewal_dir,
        config_hash,
        detector_config,
        total_batches,
        title_threshold,
        author_threshold,
        publisher_threshold,
        year_tolerance,
        early_exit_title,
        early_exit_author,
        early_exit_publisher,
        score_everything,
        minimum_combined_score,
        brute_force_missing_year,
        min_year,
        max_year,
        result_temp_dir,
    ) = batch_info

    batch_num = batch_id
    pickled_batch_path = batch_path

    # Load the batch
    with open(pickled_batch_path, "rb") as f:
        batch = load(f)

    # Clean up the pickle file
    try:
        unlink(pickled_batch_path)
    except Exception:
        pass  # Ignore cleanup errors

    # Don't log batch start - main process handles progress tracking

    # Process timing
    start_time = time()

    # Use the unpacked options
    score_everything_mode = score_everything

    # Create matcher for this batch
    matcher = DataMatcher(config=_worker_config)

    # Process stats - use the BatchStats Pydantic model
    stats = BatchStats(batch_id=batch_num)

    # Track processed publications (not skipped ones)
    processed_publications = []

    # Process each publication
    for pub in batch:
        # Skip if no year and not brute forcing
        if pub.year is None and not brute_force_missing_year:
            stats.skipped_no_year += 1
            continue

        # Add to processed list
        processed_publications.append(pub)

        # Find registration matches
        if _worker_registration_index:
            candidates = _worker_registration_index.find_candidates(pub)
            if candidates:
                copyright_pubs = [_worker_registration_index.publications[i] for i in candidates]

                if score_everything_mode:
                    match = matcher.find_best_match_ignore_thresholds(
                        pub,
                        copyright_pubs,
                        year_tolerance,
                        minimum_combined_score,
                        generic_detector=_worker_generic_detector,
                    )
                else:
                    match = matcher.find_best_match(
                        pub,
                        copyright_pubs,
                        title_threshold,
                        author_threshold,
                        publisher_threshold,
                        year_tolerance,
                        early_exit_title,
                        early_exit_author,
                        early_exit_publisher,
                        generic_detector=_worker_generic_detector,
                    )

                if match:
                    # Convert dict to MatchResult object
                    stats.registration_matches_found += 1
                    copyright_rec = match["copyright_record"]
                    scores = match["similarity_scores"]

                    match_result = MatchResult(
                        matched_title=copyright_rec["title"],
                        matched_author=copyright_rec.get("author", ""),
                        similarity_score=scores["combined"],
                        title_score=scores["title"],
                        author_score=scores["author"],
                        publisher_score=scores.get("publisher", 0.0),
                        year_difference=(
                            abs(pub.year - copyright_rec["year"])
                            if pub.year and copyright_rec.get("year")
                            else 0
                        ),
                        source_id=copyright_rec.get("source_id", ""),
                        source_type="registration",
                        matched_date=copyright_rec.get("pub_date", ""),
                        matched_publisher=copyright_rec.get("publisher"),
                        match_type=(
                            MatchType.LCCN
                            if match.get("is_lccn_match", False)
                            else (
                                MatchType.BRUTE_FORCE_WITHOUT_YEAR
                                if pub.year is None and brute_force_missing_year
                                else MatchType.SIMILARITY
                            )
                        ),
                        normalized_title=copyright_rec.get("normalized_title", ""),
                        normalized_author=copyright_rec.get("normalized_author", ""),
                        normalized_publisher=copyright_rec.get("normalized_publisher", ""),
                    )
                    pub.registration_match = match_result

                    # Handle generic title info
                    if "generic_title_info" in match and match["generic_title_info"]:
                        generic_info = match["generic_title_info"]
                        if generic_info["has_generic_title"]:
                            pub.generic_title_detected = True
                            pub.registration_generic_title = True
                            if (
                                pub.generic_detection_reason == "none"
                                or generic_info["marc_title_is_generic"]
                            ):
                                if generic_info["marc_title_is_generic"]:
                                    pub.generic_detection_reason = generic_info[
                                        "marc_detection_reason"
                                    ]
                                else:
                                    pub.generic_detection_reason = generic_info[
                                        "copyright_detection_reason"
                                    ]

        # Find renewal matches
        if _worker_renewal_index:
            candidates = _worker_renewal_index.find_candidates(pub)
            if candidates:
                renewal_pubs = [_worker_renewal_index.publications[i] for i in candidates]

                if score_everything_mode:
                    match = matcher.find_best_match_ignore_thresholds(
                        pub,
                        renewal_pubs,
                        year_tolerance,
                        minimum_combined_score,
                        generic_detector=_worker_generic_detector,
                    )
                else:
                    match = matcher.find_best_match(
                        pub,
                        renewal_pubs,
                        title_threshold,
                        author_threshold,
                        publisher_threshold,
                        year_tolerance,
                        early_exit_title,
                        early_exit_author,
                        early_exit_publisher,
                        generic_detector=_worker_generic_detector,
                    )

                if match:
                    # Convert dict to MatchResult object
                    stats.renewal_matches_found += 1
                    copyright_rec = match["copyright_record"]
                    scores = match["similarity_scores"]

                    match_result = MatchResult(
                        matched_title=copyright_rec["title"],
                        matched_author=copyright_rec.get("author", ""),
                        similarity_score=scores["combined"],
                        title_score=scores["title"],
                        author_score=scores["author"],
                        publisher_score=scores.get("publisher", 0.0),
                        year_difference=(
                            abs(pub.year - copyright_rec["year"])
                            if pub.year and copyright_rec.get("year")
                            else 0
                        ),
                        source_id=copyright_rec.get("source_id", ""),
                        source_type="renewal",
                        matched_date=copyright_rec.get("pub_date", ""),
                        matched_publisher=copyright_rec.get("publisher"),
                        match_type=(
                            MatchType.LCCN
                            if match.get("is_lccn_match", False)
                            else (
                                MatchType.BRUTE_FORCE_WITHOUT_YEAR
                                if pub.year is None and brute_force_missing_year
                                else MatchType.SIMILARITY
                            )
                        ),
                        normalized_title=copyright_rec.get("normalized_title", ""),
                        normalized_author=copyright_rec.get("normalized_author", ""),
                        normalized_publisher=copyright_rec.get("normalized_publisher", ""),
                    )
                    pub.renewal_match = match_result

                    # Handle generic title info
                    if "generic_title_info" in match and match["generic_title_info"]:
                        generic_info = match["generic_title_info"]
                        if generic_info["has_generic_title"]:
                            pub.generic_title_detected = True
                            pub.renewal_generic_title = True
                            if (
                                pub.generic_detection_reason == "none"
                                or generic_info["marc_title_is_generic"]
                            ):
                                if generic_info["marc_title_is_generic"]:
                                    pub.generic_detection_reason = generic_info[
                                        "marc_detection_reason"
                                    ]
                                else:
                                    pub.generic_detection_reason = generic_info[
                                        "copyright_detection_reason"
                                    ]

        stats.marc_count += 1  # Count actually processed records
        stats.total_comparisons += 1  # Track comparisons made

        # Determine copyright status
        pub.determine_copyright_status()

    # Calculate timing
    elapsed = time() - start_time
    stats.processing_time = elapsed

    # Save results to file (only processed publications)
    result_file_path = join(result_temp_dir, f"batch_{batch_num}_result.pkl")
    with open(result_file_path, "wb") as f:
        dump(processed_publications, f, protocol=HIGHEST_PROTOCOL)

    # Create detailed statistics dictionary for the stats file
    detailed_stats = {
        "total_records": stats.marc_count,
        "registration_matches": stats.registration_matches_found,
        "renewal_matches": stats.renewal_matches_found,
        "skipped_no_year": stats.skipped_no_year,
        "skipped_out_of_range": stats.skipped_out_of_range,
        "skipped_non_us": stats.skipped_non_us,
    }

    # Count copyright statuses
    for pub in processed_publications:
        if hasattr(pub, "copyright_status") and pub.copyright_status:
            status_key = pub.copyright_status.lower()
            detailed_stats[status_key] = detailed_stats.get(status_key, 0) + 1

    # Save statistics to separate file
    stats_file_path = join(result_temp_dir, f"batch_{batch_num}_stats.pkl")
    with open(stats_file_path, "wb") as f:
        dump(detailed_stats, f, protocol=HIGHEST_PROTOCOL)

    # Get memory usage
    process = psutil.Process(getpid())
    process.memory_info().rss / 1024 / 1024

    # Worker logs details only for exceptional cases
    # Main process handles normal progress reporting
    records_per_sec = stats.marc_count / elapsed if elapsed > 0 else 0

    # Only log if something unusual happened
    if stats.marc_count < len(batch):
        # Some records were skipped - worth noting
        skipped = len(batch) - stats.marc_count
        logger.debug(f"  Batch {batch_num}: {skipped} records skipped (no year or filtered)")

    # Log if processing was unusually slow
    if elapsed > 30 and records_per_sec < 5:
        logger.warning(
            f"  Batch {batch_num}: Slow processing detected ({records_per_sec:.1f} rec/s)"
        )

    return batch_num, result_file_path, stats
