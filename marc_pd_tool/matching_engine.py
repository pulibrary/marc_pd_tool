"""Publication matching engine for parallel batch processing"""

# Standard library imports
from logging import Formatter
from logging import INFO
from logging import StreamHandler
from logging import getLogger
from os import getpid
from re import split as re_split
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple

# Third party imports
from fuzzywuzzy import fuzz

# Local imports
from marc_pd_tool.cache_manager import CacheManager
from marc_pd_tool.default_matching import DefaultMatchingEngine
from marc_pd_tool.generic_title_detector import GenericTitleDetector
from marc_pd_tool.matching_api import MatchingEngine
from marc_pd_tool.publication import MatchResult
from marc_pd_tool.publication import Publication

logger = getLogger(__name__)


def extract_best_publisher_match(marc_publisher: str, full_text: str) -> str:
    """Extract the best matching publisher snippet from full_text"""
    if not marc_publisher or not full_text:
        return ""

    # Split on common delimiters while keeping some context
    segments = re_split(r"[,.;]\s*", full_text)

    # Find the segment that best matches the MARC publisher
    best_match = ""
    best_score = 0

    for segment in segments:
        if len(segment.strip()) > 5:  # Skip very short segments
            score = fuzz.partial_ratio(marc_publisher, segment)
            if score > best_score:
                best_score = score
                best_match = segment.strip()

    # If we found a good match, return it; otherwise return the MARC publisher
    return best_match if best_score > 70 else marc_publisher


def process_batch(
    batch_info: Tuple[
        int, List[Publication], str, str, str, str, Dict, int, int, int, int, int, int
    ],
) -> Tuple[int, List[Publication], Dict]:
    """
    Process a single batch of MARC records against pre-built indexes.
    This function runs in a separate process.
    """
    (
        batch_id,
        marc_batch,
        cache_dir,
        copyright_dir,
        renewal_dir,
        config_hash,
        detector_config,
        total_batches,
        title_threshold,
        author_threshold,
        year_tolerance,
        early_exit_title,
        early_exit_author,
    ) = batch_info

    # Set up logging for this process - needed for multiprocessing
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

    # Configure the batch logger to use the same handler as root logger
    if not process_logger.handlers and root_logger.handlers:
        for handler in root_logger.handlers:
            process_logger.addHandler(handler)
        process_logger.setLevel(root_logger.level)
        # Prevent propagation to avoid duplicate messages
        process_logger.propagate = False

    stats = {
        "batch_id": batch_id,
        "marc_count": len(marc_batch),
        "registration_matches_found": 0,
        "renewal_matches_found": 0,
        "total_comparisons": 0,
        "us_records": 0,
        "non_us_records": 0,
        "unknown_country_records": 0,
    }

    # Log batch start with process logger (same as completion messages)
    process_logger.info(
        f"Batch {batch_id}/{total_batches}: Process {getpid()} starting with {len(marc_batch)} MARC records"
    )

    # Load pre-built indexes and detector directly from cache
    if not cache_dir:
        raise RuntimeError("No cache directory provided to worker process - this shouldn't occur")

    cache_manager = CacheManager(cache_dir)

    process_logger.debug(f"Batch {batch_id}/{total_batches}: Loading indexes from cache")
    cached_indexes = cache_manager.get_cached_indexes(copyright_dir, renewal_dir, config_hash)
    if cached_indexes is None:
        raise RuntimeError(f"Failed to load indexes from cache in worker process {batch_id}")
    registration_index, renewal_index = cached_indexes

    process_logger.debug(
        f"Batch {batch_id}/{total_batches}: Loading generic title detector from cache"
    )
    generic_detector = cache_manager.get_cached_generic_detector(
        copyright_dir, renewal_dir, detector_config
    )
    if generic_detector is None and not detector_config.get("disabled", False):
        raise RuntimeError(
            f"Failed to load generic title detector from cache in worker process {batch_id}"
        )

    process_logger.debug(
        f"Batch {batch_id}/{total_batches}: {registration_index.size():,} registration entries, {renewal_index.size():,} renewal entries"
    )

    process_logger.debug(f"Batch {batch_id}/{total_batches}: Indexes loaded successfully")

    # Process each MARC record in the batch
    for i, marc_pub in enumerate(marc_batch):

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
        reg_match = find_best_match(
            marc_pub,
            reg_candidates,
            title_threshold,
            author_threshold,
            year_tolerance,
            60,  # publisher_threshold
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
            )
            marc_pub.set_registration_match(match_result)

            # Store generic title detection info for registration match
            if "generic_title_info" in reg_match:
                generic_info = reg_match["generic_title_info"]
                if generic_info["has_generic_title"]:
                    marc_pub.generic_title_detected = True
                    marc_pub.registration_generic_title = True
                    # Use MARC detection reason if MARC title is generic, otherwise copyright reason
                    if generic_info["marc_title_is_generic"]:
                        marc_pub.generic_detection_reason = generic_info["marc_detection_reason"]
                    else:
                        marc_pub.generic_detection_reason = generic_info[
                            "copyright_detection_reason"
                        ]

            stats["registration_matches_found"] += 1

        # Find renewal candidates using index
        ren_candidates = renewal_index.get_candidates_list(marc_pub, year_tolerance)
        ren_match = find_best_match(
            marc_pub,
            ren_candidates,
            title_threshold,
            author_threshold,
            year_tolerance,
            60,  # publisher_threshold
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
            )
            marc_pub.set_renewal_match(match_result)

            # Store generic title detection info for renewal match
            if "generic_title_info" in ren_match:
                generic_info = ren_match["generic_title_info"]
                if generic_info["has_generic_title"]:
                    marc_pub.generic_title_detected = True
                    marc_pub.renewal_generic_title = True
                    # Update detection reason if not already set, or if MARC title is generic
                    if (
                        marc_pub.generic_detection_reason == "none"
                        or generic_info["marc_title_is_generic"]
                    ):
                        if generic_info["marc_title_is_generic"]:
                            marc_pub.generic_detection_reason = generic_info[
                                "marc_detection_reason"
                            ]
                        else:
                            marc_pub.generic_detection_reason = generic_info[
                                "copyright_detection_reason"
                            ]

            stats["renewal_matches_found"] += 1

        stats["total_comparisons"] += len(reg_candidates) + len(ren_candidates)

        # Determine copyright status based on matches and country
        marc_pub.determine_copyright_status()

    process_logger.debug(
        f"Batch {batch_id}/{total_batches} complete: {stats['registration_matches_found']} registration matches, "
        f"{stats['renewal_matches_found']} renewal matches from {stats['marc_count']} records"
    )
    process_logger.debug(
        f"Batch {batch_id}/{total_batches} country breakdown: {stats['us_records']} US, "
        f"{stats['non_us_records']} Non-US, {stats['unknown_country_records']} Unknown"
    )

    return batch_id, marc_batch, stats


def find_best_match(
    marc_pub: Publication,
    copyright_pubs: List[Publication],
    title_threshold: int,
    author_threshold: int,
    year_tolerance: int,
    publisher_threshold: int = 60,
    early_exit_title: int = 95,
    early_exit_author: int = 90,
    generic_detector: GenericTitleDetector = None,
    matching_engine: Optional[MatchingEngine] = None,
) -> Optional[Dict]:
    """Find the best matching copyright publication for a MARC record

    This function maintains backward compatibility while delegating to the new API.

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
        matching_engine: Optional custom matching engine (uses default if None)

    Returns:
        Dictionary with match information or None if no match found
    """
    if matching_engine is None:
        matching_engine = DefaultMatchingEngine()

    return matching_engine.find_best_match(
        marc_pub,
        copyright_pubs,
        title_threshold,
        author_threshold,
        year_tolerance,
        publisher_threshold,
        early_exit_title,
        early_exit_author,
        generic_detector,
    )
