# marc_pd_tool/processing/matching_engine.py

"""Data matching engine for comparing MARC records against copyright/renewal data"""

# Standard library imports
from logging import Formatter
from logging import INFO
from logging import StreamHandler
from logging import getLogger
from os import getpid
from time import time
from typing import cast

# Local imports
from marc_pd_tool.data.enums import MatchType
from marc_pd_tool.data.publication import MatchResult
from marc_pd_tool.data.publication import Publication
from marc_pd_tool.infrastructure.cache_manager import CacheManager
from marc_pd_tool.infrastructure.config_loader import ConfigLoader
from marc_pd_tool.processing.similarity_calculator import SimilarityCalculator
from marc_pd_tool.processing.text_processing import GenericTitleDetector
from marc_pd_tool.processing.text_processing import extract_best_publisher_match
from marc_pd_tool.utils.mixins import ConfigurableMixin
from marc_pd_tool.utils.types import BatchProcessingInfo
from marc_pd_tool.utils.types import BatchStats
from marc_pd_tool.utils.types import MatchResultDict

logger = getLogger(__name__)


class DataMatcher(ConfigurableMixin):
    """Data matching engine for comparing MARC records against copyright/renewal data"""

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
        self.config = self._init_config(config)

        # Use default similarity calculator if none provided
        if similarity_calculator is None:
            similarity_calculator = SimilarityCalculator(self.config)
        self.similarity_calculator = similarity_calculator

        # Get adaptive scoring configuration
        config_dict = self.config.get_config()

        # Get weight values using safe navigation
        title_weight = self._get_config_value(
            config_dict, "matching.adaptive_weighting.title_weight", 0.5
        )
        self.default_title_weight = (
            float(title_weight) if isinstance(title_weight, (int, float, str)) else 0.5
        )

        author_weight = self._get_config_value(
            config_dict, "matching.adaptive_weighting.author_weight", 0.3
        )
        self.default_author_weight = (
            float(author_weight) if isinstance(author_weight, (int, float, str)) else 0.3
        )

        publisher_weight = self._get_config_value(
            config_dict, "matching.adaptive_weighting.publisher_weight", 0.2
        )
        self.default_publisher_weight = (
            float(publisher_weight) if isinstance(publisher_weight, (int, float, str)) else 0.2
        )

        penalty = self._get_config_value(
            config_dict, "matching.adaptive_weighting.generic_title_penalty", 0.8
        )
        self.generic_title_penalty = (
            float(penalty) if isinstance(penalty, (int, float, str)) else 0.8
        )

    def find_best_match(
        self,
        marc_pub: Publication,
        copyright_pubs: list[Publication],
        title_threshold: int,
        author_threshold: int,
        year_tolerance: int,
        publisher_threshold: int,
        early_exit_title: int,
        early_exit_author: int,
        generic_detector: GenericTitleDetector | None = None,
    ) -> MatchResultDict | None:
        """Find the best matching copyright publication using word-based matching

        This method maintains full compatibility with the existing API while using
        the word-based matching algorithm with stemming and stopwords.

        Args:
            marc_pub: MARC publication to match
            copyright_pubs: List of copyright/renewal publications to search
            title_threshold: Minimum title similarity score (0-100)
            author_threshold: Minimum author similarity score (0-100)
            year_tolerance: Maximum year difference for matching
            publisher_threshold: Minimum publisher similarity score (0-100)
            early_exit_title: Title score for early termination (0-100)
            early_exit_author: Author score for early termination (0-100)
            generic_detector: Optional generic title detector

        Returns:
            Dictionary with match information or None if no match found
        """
        if not copyright_pubs:
            return None

        best_match = None
        best_score = 0.0

        for copyright_pub in copyright_pubs:
            # Year filtering (maintain existing logic)
            if marc_pub.year and copyright_pub.year:
                year_diff = abs(marc_pub.year - copyright_pub.year)
                if year_diff > year_tolerance:
                    continue

            # LCCN exact matching - highest priority with perfect score
            if (
                marc_pub.normalized_lccn
                and copyright_pub.normalized_lccn
                and marc_pub.normalized_lccn == copyright_pub.normalized_lccn
            ):
                # Perfect match - return immediately with 100% scores
                return self._create_match_result(
                    copyright_pub,
                    100.0,  # title_score
                    100.0,  # author_score
                    100.0,  # publisher_score
                    100.0,  # combined_score
                    marc_pub,
                    generic_detector,
                    is_lccn_match=True,
                )

            # Calculate individual similarity scores using word-based calculator with publication language
            title_score = self.similarity_calculator.calculate_title_similarity(
                marc_pub.title, copyright_pub.title, marc_pub.language_code
            )

            # Use dual author scoring with publication language
            author_score = 0.0
            has_author_data = False
            if marc_pub.author and copyright_pub.author:
                has_author_data = True
                author_score = max(
                    author_score,
                    self.similarity_calculator.calculate_author_similarity(
                        marc_pub.author, copyright_pub.author, marc_pub.language_code
                    ),
                )
            if marc_pub.main_author and copyright_pub.author:
                has_author_data = True
                author_score = max(
                    author_score,
                    self.similarity_calculator.calculate_author_similarity(
                        marc_pub.main_author, copyright_pub.author, marc_pub.language_code
                    ),
                )

            # Publisher scoring with full_text support for renewals and publication language
            publisher_score = self.similarity_calculator.calculate_publisher_similarity(
                marc_pub.publisher,
                copyright_pub.publisher,
                getattr(copyright_pub, "full_text", ""),
                marc_pub.language_code,
            )

            # Apply thresholds (maintain existing logic)
            if title_score < title_threshold:
                continue
            # Only apply author threshold if there's author data to compare
            if has_author_data and author_score < author_threshold:
                continue
            if (
                publisher_score < publisher_threshold
                and marc_pub.publisher
                and copyright_pub.publisher
            ):
                continue

            # Early exit conditions (maintain existing logic)
            # For early exit, require both high title AND high author scores when author data exists
            # If no author data, only require high title score
            if title_score >= early_exit_title and (
                not has_author_data or author_score >= early_exit_author
            ):
                # Found high-confidence match, return immediately
                combined_score = self._combine_scores(
                    title_score,
                    author_score,
                    publisher_score,
                    marc_pub,
                    copyright_pub,
                    generic_detector,
                )

                return self._create_match_result(
                    copyright_pub,
                    title_score,
                    author_score,
                    publisher_score,
                    combined_score,
                    marc_pub,
                    generic_detector,
                )

            # Combine scores using adaptive weighting
            combined_score = self._combine_scores(
                title_score,
                author_score,
                publisher_score,
                marc_pub,
                copyright_pub,
                generic_detector,
            )

            # Track best match
            if combined_score > best_score:
                best_score = combined_score
                best_match = self._create_match_result(
                    copyright_pub,
                    title_score,
                    author_score,
                    publisher_score,
                    combined_score,
                    marc_pub,
                    generic_detector,
                )

        return best_match

    def find_best_match_ignore_thresholds(
        self,
        marc_pub: Publication,
        copyright_pubs: list[Publication],
        year_tolerance: int,
        early_exit_title: int,
        early_exit_author: int,
        generic_detector: GenericTitleDetector | None = None,
        minimum_combined_score: float | None = None,
    ) -> MatchResultDict | None:
        """Find the best matching copyright publication ignoring similarity thresholds

        This method returns the highest-scoring match found, but can enforce
        a minimum combined score. Used for threshold optimization analysis.

        Args:
            minimum_combined_score: Optional minimum combined score (0-100).
                                  If provided, matches below this score are rejected.
        """
        best_match = None
        best_score = -1.0  # Start with -1 so even 0 scores are captured

        for copyright_pub in copyright_pubs:
            # Check year tolerance filter (still applied even in score-everything mode)
            if marc_pub.year and copyright_pub.year:
                if abs(marc_pub.year - copyright_pub.year) > year_tolerance:
                    continue

            # LCCN exact matching - highest priority with perfect score
            if (
                marc_pub.normalized_lccn
                and copyright_pub.normalized_lccn
                and marc_pub.normalized_lccn == copyright_pub.normalized_lccn
            ):
                # Perfect match - return immediately with 100% scores
                return self._create_match_result(
                    copyright_pub,
                    100.0,  # title_score
                    100.0,  # author_score
                    100.0,  # publisher_score
                    100.0,  # combined_score
                    marc_pub,
                    generic_detector,
                    is_lccn_match=True,
                )

            # Calculate similarity scores using word-based approach
            title_score = self.similarity_calculator.calculate_title_similarity(
                marc_pub.title, copyright_pub.title, marc_pub.language_code or "eng"
            )

            # Use dual author scoring with publication language (same as regular find_best_match)
            author_score = 0.0
            if marc_pub.author and copyright_pub.author:
                author_score = max(
                    author_score,
                    self.similarity_calculator.calculate_author_similarity(
                        marc_pub.author, copyright_pub.author, marc_pub.language_code or "eng"
                    ),
                )
            if marc_pub.main_author and copyright_pub.author:
                author_score = max(
                    author_score,
                    self.similarity_calculator.calculate_author_similarity(
                        marc_pub.main_author, copyright_pub.author, marc_pub.language_code or "eng"
                    ),
                )

            publisher_score = self.similarity_calculator.calculate_publisher_similarity(
                marc_pub.publisher,
                copyright_pub.publisher,
                getattr(copyright_pub, "full_text", ""),
                marc_pub.language_code or "eng",
            )

            # Calculate combined weighted score using adaptive weighting
            combined_score = self._combine_scores(
                title_score,
                author_score,
                publisher_score,
                marc_pub,
                copyright_pub,
                generic_detector,
            )

            # Always accept the best score found (no threshold requirements)
            if combined_score > best_score:
                best_score = combined_score
                best_match = self._create_match_result(
                    copyright_pub,
                    title_score,
                    author_score,
                    publisher_score,
                    combined_score,
                    marc_pub,
                    generic_detector,
                )

                # Early termination: Only exit if we have BOTH title and author with very high confidence
                has_author_data = (marc_pub.author and copyright_pub.author) or (
                    marc_pub.main_author and copyright_pub.author
                )
                if (
                    title_score >= early_exit_title
                    and has_author_data
                    and author_score >= early_exit_author
                ):
                    break

        # Apply minimum combined score threshold if specified
        if minimum_combined_score is not None and best_match:
            if best_match["similarity_scores"]["combined"] < minimum_combined_score:
                return None  # Reject match below minimum threshold

        return best_match

    def _combine_scores(
        self,
        title_score: float,
        author_score: float,
        publisher_score: float,
        marc_pub: Publication,
        copyright_pub: Publication,
        generic_detector: GenericTitleDetector | None = None,
    ) -> float:
        """Combine individual scores using adaptive weighting

        Redistributes weights when fields are missing to avoid zero penalties.

        Args:
            title_score: Title similarity score (0-100)
            author_score: Author similarity score (0-100)
            publisher_score: Publisher similarity score (0-100)
            marc_pub: MARC publication object
            copyright_pub: Copyright publication object
            generic_detector: Optional generic title detector

        Returns:
            Combined weighted score (0-100)
        """
        # Start with default weights
        title_weight = self.default_title_weight
        author_weight = self.default_author_weight
        publisher_weight = self.default_publisher_weight

        # Check which fields are missing and redistribute weights
        has_author = (marc_pub.author and copyright_pub.author) or (
            marc_pub.main_author and copyright_pub.author
        )
        has_publisher = marc_pub.publisher and (
            copyright_pub.publisher or getattr(copyright_pub, "full_text", "")
        )

        if not has_author and not has_publisher:
            # Only title available - give it full weight
            title_weight = 1.0
            author_weight = 0.0
            publisher_weight = 0.0
        elif not has_author:
            # Title and publisher available - redistribute author weight
            title_weight += author_weight * 0.7  # Most to title
            publisher_weight += author_weight * 0.3  # Some to publisher
            author_weight = 0.0
        elif not has_publisher:
            # Title and author available - redistribute publisher weight
            title_weight += publisher_weight * 0.6  # Most to title
            author_weight += publisher_weight * 0.4  # Some to author
            publisher_weight = 0.0

        # Calculate base weighted score
        weighted_score = (
            title_score * title_weight
            + author_score * author_weight
            + publisher_score * publisher_weight
        )

        # Apply generic title penalty if either title is generic
        if generic_detector:
            marc_is_generic = generic_detector.is_generic(
                marc_pub.title, marc_pub.language_code or "eng"
            )
            copyright_is_generic = generic_detector.is_generic(
                copyright_pub.title, copyright_pub.language_code or "eng"
            )

            if marc_is_generic or copyright_is_generic:
                weighted_score *= self.generic_title_penalty

        return weighted_score

    def _create_match_result(
        self,
        copyright_pub: Publication,
        title_score: float,
        author_score: float,
        publisher_score: float,
        combined_score: float,
        marc_pub: Publication,
        generic_detector: GenericTitleDetector | None,
        is_lccn_match: bool = False,
    ) -> MatchResultDict:
        """Create match result dictionary (maintain existing format)

        Args:
            copyright_pub: Matched copyright publication
            title_score: Title similarity score
            author_score: Author similarity score
            publisher_score: Publisher similarity score
            combined_score: Combined similarity score
            marc_pub: MARC publication object
            generic_detector: Generic title detector

        Returns:
            Match result dictionary
        """
        result: MatchResultDict = {
            "match": None,  # Will be set later if match is created
            "copyright_record": {
                "title": copyright_pub.original_title or copyright_pub.title,
                "author": copyright_pub.original_author or copyright_pub.author,
                "year": copyright_pub.year,
                "publisher": copyright_pub.original_publisher or copyright_pub.publisher,
                "source_id": copyright_pub.source_id or "",
                "pub_date": copyright_pub.pub_date or "",
                "full_text": getattr(copyright_pub, "full_text", ""),
            },
            "similarity_scores": {
                "title": title_score,
                "author": author_score,
                "publisher": publisher_score,
                "combined": combined_score,
            },
            "is_lccn_match": is_lccn_match,
            "generic_title_info": None,  # Will be set if generic detector is used
        }

        # Add generic title detection info if available
        if generic_detector:
            marc_is_generic = generic_detector.is_generic(
                marc_pub.title, marc_pub.language_code or "eng"
            )
            copyright_is_generic = generic_detector.is_generic(
                copyright_pub.title, copyright_pub.language_code or "eng"
            )

            result["generic_title_info"] = {
                "has_generic_title": marc_is_generic or copyright_is_generic,
                "marc_title_is_generic": marc_is_generic,
                "copyright_title_is_generic": copyright_is_generic,
                "marc_detection_reason": (
                    generic_detector.get_detection_reason(
                        marc_pub.title, marc_pub.language_code or "eng"
                    )
                    if marc_is_generic
                    else "none"
                ),
                "copyright_detection_reason": (
                    generic_detector.get_detection_reason(
                        copyright_pub.title, copyright_pub.language_code or "eng"
                    )
                    if copyright_is_generic
                    else "none"
                ),
            }

        return result


# Global storage for worker-specific data
_worker_data = {}

# Global storage for shared data (Linux fork mode)
_shared_data = {}


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

    This function is called once when a worker process starts.
    It loads all heavy data structures (indexes, detector, etc.) once
    and stores them for reuse across all batches processed by this worker.
    """
    global _worker_data
    process_logger = getLogger(__name__)
    pid = getpid()

    try:
        process_logger.info(f"Worker {pid} initializing...")

        # Load indexes once per worker
        cache_manager = CacheManager(cache_dir)

        process_logger.debug(f"Worker {pid}: Loading indexes from cache")
        start_time = time()
        cached_indexes = cache_manager.get_cached_indexes(
            copyright_dir, renewal_dir, config_hash, min_year, max_year, brute_force
        )
        load_time = time() - start_time

        if cached_indexes is None:
            raise RuntimeError(f"Worker {pid}: Failed to load indexes from cache")

        process_logger.info(f"Worker {pid}: Index loading took {load_time:.1f} seconds")

        registration_index, renewal_index = cached_indexes
        renewal_size = renewal_index.size() if renewal_index else 0
        process_logger.info(
            f"Worker {pid}: Loaded {registration_index.size():,} registration, "
            f"{renewal_size:,} renewal entries"
        )

        # Log memory usage
        # Third party imports
        import psutil

        process = psutil.Process(pid)
        mem_mb = process.memory_info().rss / 1024 / 1024
        process_logger.info(f"Worker {pid}: Current memory usage: {mem_mb:.1f}MB")

        # Load generic title detector
        process_logger.debug(f"Worker {pid}: Loading generic title detector")
        generic_detector = cache_manager.get_cached_generic_detector(
            copyright_dir, renewal_dir, detector_config
        )
        if generic_detector is None and not detector_config.get("disabled", False):
            process_logger.warning(f"Worker {pid}: No generic title detector loaded")

        # Initialize matching engine
        matching_engine = DataMatcher()

        # Store everything for reuse
        _worker_data = {
            "registration_index": registration_index,
            "renewal_index": renewal_index,
            "generic_detector": generic_detector,
            "matching_engine": matching_engine,
            "cache_manager": cache_manager,
        }

        process_logger.info(f"Worker {pid} initialized successfully")

    except Exception as e:
        process_logger.error(f"Worker {pid} initialization failed: {e}")
        raise


def process_batch(batch_info: BatchProcessingInfo) -> tuple[int, str, BatchStats]:
    """
    Process a single batch of MARC records against pre-built indexes.
    This function runs in a separate process.

    Returns:
        Tuple of (batch_id, result_file_path, batch_stats)
    """
    (
        batch_id,
        batch_path,  # Changed from marc_batch to batch_path
        cache_dir,
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
        score_everything_mode,
        minimum_combined_score,
        brute_force_missing_year,
        min_year,
        max_year,
        result_temp_dir,  # Directory to save result pickle files
    ) = batch_info

    # Set up logging for this process first - needed for multiprocessing
    root_logger = getLogger()
    if not root_logger.handlers:
        # Configure logging in worker process if not already configured
        console_handler = StreamHandler()
        console_handler.setLevel(INFO)
        formatter = Formatter("%(asctime)s - %(levelname)s - %(message)s")
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
        root_logger.setLevel(INFO)

    process_logger = getLogger(f"batch_{batch_id}")

    # Load the batch from pickle file
    # Standard library imports
    import os
    import pickle

    try:
        with open(batch_path, "rb") as f:
            marc_batch = pickle.load(f)

        # Delete the batch file to free disk space
        os.unlink(batch_path)
        process_logger.debug(f"Deleted batch file: {batch_path}")

    except Exception as e:
        process_logger.error(f"Failed to load batch from {batch_path}: {e}")
        raise

    # Configure the batch logger to use the same handler as root logger
    if not process_logger.handlers and root_logger.handlers:
        for handler in root_logger.handlers:
            process_logger.addHandler(handler)
        process_logger.setLevel(root_logger.level)
        # Prevent propagation to avoid duplicate messages
        process_logger.propagate = False

    stats: BatchStats = {
        "batch_id": batch_id,
        "marc_count": 0,  # Will be updated with actual processed count
        "registration_matches_found": 0,
        "renewal_matches_found": 0,
        "total_comparisons": 0,
        "us_records": 0,
        "non_us_records": 0,
        "unknown_country_records": 0,
    }

    try:
        # Log batch start
        process_logger.info(
            f"Batch {batch_id}/{total_batches}: Process {getpid()} starting with {len(marc_batch)} MARC records"
        )

        # Use pre-loaded data from worker initialization
        global _worker_data
        if not _worker_data:
            raise RuntimeError(
                f"Worker not properly initialized - _worker_data is empty. "
                f"This usually means the worker initializer wasn't called."
            )

        # Get pre-loaded components
        registration_index = _worker_data["registration_index"]
        renewal_index = _worker_data["renewal_index"]
        generic_detector = _worker_data["generic_detector"]
        matching_engine = _worker_data["matching_engine"]

        # Track actually processed publications
        processed_publications = []

        # Process each MARC record in the batch
        for i, marc_pub in enumerate(marc_batch):

            # Skip records without year data unless brute-force mode is enabled
            if marc_pub.year is None and not brute_force_missing_year:
                process_logger.debug(f"Skipping MARC record {marc_pub.source_id} - no year data")
                continue

            # Count by country classification
            if hasattr(marc_pub, "country_classification"):
                if marc_pub.country_classification.value == "US":
                    stats["us_records"] += 1
                elif marc_pub.country_classification.value == "Non-US":
                    stats["non_us_records"] += 1
                else:
                    stats["unknown_country_records"] += 1

            # Find registration candidates using index
            reg_candidates = registration_index.get_candidates_list(marc_pub, year_tolerance)

            if score_everything_mode:
                reg_match = matching_engine.find_best_match_ignore_thresholds(
                    marc_pub,
                    reg_candidates,
                    year_tolerance,
                    early_exit_title,
                    early_exit_author,
                    generic_detector,
                    minimum_combined_score,
                )
            else:
                reg_match = matching_engine.find_best_match(
                    marc_pub,
                    reg_candidates,
                    title_threshold,
                    author_threshold,
                    year_tolerance,
                    publisher_threshold,
                    early_exit_title,
                    early_exit_author,
                    generic_detector,
                )

            # Note: Metaphone fallback matching removed to reduce false positives

            if reg_match:
                match_result = MatchResult(
                    matched_title=reg_match["copyright_record"]["title"],
                    matched_author=reg_match["copyright_record"]["author"],
                    similarity_score=reg_match["similarity_scores"]["combined"],
                    title_score=reg_match["similarity_scores"]["title"],
                    author_score=reg_match["similarity_scores"]["author"],
                    publisher_score=reg_match["similarity_scores"]["publisher"],
                    year_difference=(
                        abs(marc_pub.year - reg_match["copyright_record"]["year"])
                        if marc_pub.year and reg_match["copyright_record"]["year"]
                        else 0
                    ),
                    source_id=reg_match["copyright_record"]["source_id"],
                    matched_publisher=reg_match["copyright_record"]["publisher"],
                    source_type="registration",
                    matched_date=reg_match["copyright_record"]["pub_date"],
                    match_type=(
                        MatchType.LCCN
                        if reg_match.get("is_lccn_match", False)
                        else (
                            MatchType.BRUTE_FORCE_WITHOUT_YEAR
                            if marc_pub.year is None and brute_force_missing_year
                            else MatchType.SIMILARITY
                        )
                    ),
                )
                marc_pub.set_registration_match(match_result)

                # Store generic title detection info for registration match
                if "generic_title_info" in reg_match:
                    generic_info = cast(dict[str, bool | str], reg_match["generic_title_info"])
                    if cast(bool, generic_info["has_generic_title"]):
                        marc_pub.generic_title_detected = True
                        marc_pub.registration_generic_title = True
                        # Use MARC detection reason if MARC title is generic, otherwise copyright reason
                        if cast(bool, generic_info["marc_title_is_generic"]):
                            marc_pub.generic_detection_reason = cast(
                                str, generic_info["marc_detection_reason"]
                            )
                        else:
                            marc_pub.generic_detection_reason = cast(
                                str, generic_info["copyright_detection_reason"]
                            )

                stats["registration_matches_found"] += 1

            # Find renewal candidates using index
            ren_candidates = (
                renewal_index.get_candidates_list(marc_pub, year_tolerance) if renewal_index else []
            )

            if score_everything_mode:
                ren_match = matching_engine.find_best_match_ignore_thresholds(
                    marc_pub,
                    ren_candidates,
                    year_tolerance,
                    early_exit_title,
                    early_exit_author,
                    generic_detector,
                    minimum_combined_score,
                )
            else:
                ren_match = matching_engine.find_best_match(
                    marc_pub,
                    ren_candidates,
                    title_threshold,
                    author_threshold,
                    year_tolerance,
                    publisher_threshold,
                    early_exit_title,
                    early_exit_author,
                    generic_detector,
                )

            # Note: Metaphone fallback matching removed to reduce false positives

            if ren_match:
                match_result = MatchResult(
                    matched_title=ren_match["copyright_record"]["title"],
                    matched_author=ren_match["copyright_record"]["author"],
                    similarity_score=ren_match["similarity_scores"]["combined"],
                    title_score=ren_match["similarity_scores"]["title"],
                    author_score=ren_match["similarity_scores"]["author"],
                    publisher_score=ren_match["similarity_scores"]["publisher"],
                    year_difference=(
                        abs(marc_pub.year - ren_match["copyright_record"]["year"])
                        if marc_pub.year and ren_match["copyright_record"]["year"]
                        else 0
                    ),
                    source_id=ren_match["copyright_record"]["source_id"],
                    matched_publisher=extract_best_publisher_match(
                        marc_pub.original_publisher, ren_match["copyright_record"]["full_text"]
                    ),
                    source_type="renewal",
                    matched_date=ren_match["copyright_record"]["pub_date"],
                    match_type=(
                        MatchType.LCCN
                        if ren_match.get("is_lccn_match", False)
                        else (
                            MatchType.BRUTE_FORCE_WITHOUT_YEAR
                            if marc_pub.year is None and brute_force_missing_year
                            else MatchType.SIMILARITY
                        )
                    ),
                )
                marc_pub.set_renewal_match(match_result)

                # Store generic title detection info for renewal match
                if "generic_title_info" in ren_match:
                    generic_info = cast(dict[str, bool | str], ren_match["generic_title_info"])
                    if cast(bool, generic_info["has_generic_title"]):
                        marc_pub.generic_title_detected = True
                        marc_pub.renewal_generic_title = True
                        # Update detection reason if not already set, or if MARC title is generic
                        if marc_pub.generic_detection_reason == "none" or cast(
                            bool, generic_info["marc_title_is_generic"]
                        ):
                            if cast(bool, generic_info["marc_title_is_generic"]):
                                marc_pub.generic_detection_reason = cast(
                                    str, generic_info["marc_detection_reason"]
                                )
                            else:
                                marc_pub.generic_detection_reason = cast(
                                    str, generic_info["copyright_detection_reason"]
                                )

                stats["renewal_matches_found"] += 1

            stats["total_comparisons"] += len(reg_candidates) + len(ren_candidates)

            # Determine copyright status based on matches and country
            marc_pub.determine_copyright_status()

            # Add to processed publications list
            processed_publications.append(marc_pub)

        # Update stats to reflect actual processed count
        stats["marc_count"] = len(processed_publications)

        process_logger.info(
            f"Batch {batch_id}/{total_batches} complete: {stats['registration_matches_found']} registration matches, "
            f"{stats['renewal_matches_found']} renewal matches from {stats['marc_count']} records"
        )
        process_logger.debug(
            f"Batch {batch_id}/{total_batches} country breakdown: {stats['us_records']} US, "
            f"{stats['non_us_records']} Non-US, {stats['unknown_country_records']} Unknown"
        )

        # Save results to pickle file instead of returning through queue
        # Standard library imports
        import os

        result_file_path = os.path.join(result_temp_dir, f"result_{batch_id:05d}.pkl")
        stats_file_path = os.path.join(result_temp_dir, f"stats_{batch_id:05d}.pkl")

        try:
            # Save publications
            with open(result_file_path, "wb") as f:
                pickle.dump(processed_publications, f, protocol=pickle.HIGHEST_PROTOCOL)

            # Calculate detailed statistics for the main process
            detailed_stats = {
                "total_records": len(processed_publications),
                "us_records": sum(
                    1 for p in processed_publications if p.country_classification.value == "US"
                ),
                "non_us_records": sum(
                    1 for p in processed_publications if p.country_classification.value == "Non-US"
                ),
                "unknown_country": sum(
                    1 for p in processed_publications if p.country_classification.value == "Unknown"
                ),
                "registration_matches": sum(
                    1 for p in processed_publications if p.has_registration_match()
                ),
                "renewal_matches": sum(1 for p in processed_publications if p.has_renewal_match()),
                "no_matches": sum(
                    1
                    for p in processed_publications
                    if not p.has_registration_match() and not p.has_renewal_match()
                ),
            }

            # Add copyright status counts
            for pub in processed_publications:
                if hasattr(pub, "copyright_status") and pub.copyright_status:
                    status_key = pub.copyright_status.value.lower()
                    if status_key not in detailed_stats:
                        detailed_stats[status_key] = 0
                    detailed_stats[status_key] += 1

            # Save detailed statistics separately
            with open(stats_file_path, "wb") as f:
                pickle.dump(detailed_stats, f, protocol=pickle.HIGHEST_PROTOCOL)

            process_logger.debug(
                f"Batch {batch_id}: Saved {len(processed_publications)} publications and statistics"
            )

            # Return just the file paths and basic stats (small data)
            return batch_id, result_file_path, stats

        except Exception as e:
            process_logger.error(f"Failed to save results for batch {batch_id}: {e}")
            raise

    except Exception as e:
        process_logger.error(f"Error in batch {batch_id}: {str(e)}")
        process_logger.error(f"Error type: {type(e).__name__}")
        # Standard library imports
        import traceback

        process_logger.error(f"Traceback:\n{traceback.format_exc()}")

        # For error case, save empty results to maintain consistency
        # Standard library imports
        import os

        result_file_path = os.path.join(result_temp_dir, f"result_{batch_id:05d}_failed.pkl")
        try:
            with open(result_file_path, "wb") as f:
                pickle.dump([], f, protocol=pickle.HIGHEST_PROTOCOL)
        except:
            pass

        # Return empty results but include the batch_id so we know which failed
        return batch_id, result_file_path, stats
