"""Batch processing functions for parallel publication matching"""

# Standard library imports
from csv import writer
from logging import DEBUG
from logging import getLogger
from os import getpid
from pickle import load
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple

# Third party imports
from fuzzywuzzy import fuzz
from fuzzywuzzy import process

# Local imports
from marc_pd_tool.generic_title_detector import GenericTitleDetector
from marc_pd_tool.publication import MatchResult
from marc_pd_tool.publication import Publication

logger = getLogger(__name__)


def extract_best_publisher_match(marc_publisher: str, full_text: str) -> str:
    """Extract the best matching publisher snippet from full_text"""
    if not marc_publisher or not full_text:
        return ""

    # Split full_text into potential publisher segments (around commas, periods)
    # Standard library imports
    import re

    # Split on common delimiters while keeping some context
    segments = re.split(r"[,.;]\s*", full_text)

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
    batch_info: Tuple[int, List[Publication], str, str, str, int, int, int, int, int, int],
) -> Tuple[int, List[Publication], Dict]:
    """
    Process a single batch of MARC records against pre-built indexes.
    This function runs in a separate process.
    """
    (
        batch_id,
        marc_batch,
        registration_index_file,
        renewal_index_file,
        generic_detector_file,
        total_batches,
        title_threshold,
        author_threshold,
        year_tolerance,
        early_exit_title,
        early_exit_author,
    ) = batch_info

    # Set up logging for this process
    process_logger = getLogger(f"batch_{batch_id}")

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

    process_logger.info(
        f"Batch {batch_id}/{total_batches}: Process {getpid()} starting with {len(marc_batch)} MARC records"
    )

    # Load pre-built indexes from pickle files
    process_logger.info(
        f"Batch {batch_id}/{total_batches}: Loading registration index from {registration_index_file}"
    )
    with open(registration_index_file, "rb") as f:
        registration_index = load(f)

    process_logger.info(
        f"Batch {batch_id}/{total_batches}: Loading renewal index from {renewal_index_file}"
    )
    with open(renewal_index_file, "rb") as f:
        renewal_index = load(f)

    process_logger.info(
        f"Batch {batch_id}/{total_batches}: Loading generic title detector from {generic_detector_file}"
    )
    with open(generic_detector_file, "rb") as f:
        generic_detector = load(f)

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

    process_logger.info(
        f"Batch {batch_id}/{total_batches} complete: {stats['registration_matches_found']} registration matches, "
        f"{stats['renewal_matches_found']} renewal matches from {stats['marc_count']} records"
    )
    process_logger.info(
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
) -> Optional[Dict]:
    """Find the best matching copyright publication for a MARC record"""
    best_score = 0
    best_match = None

    for copyright_pub in copyright_pubs:
        # Year filtering
        if marc_pub.year and copyright_pub.year:
            if abs(marc_pub.year - copyright_pub.year) > year_tolerance:
                continue

        # Calculate similarity scores
        title_score = fuzz.ratio(marc_pub.title, copyright_pub.title)

        # Skip if title similarity is too low
        if title_score < title_threshold:
            continue

        author_score = (
            fuzz.ratio(marc_pub.author, copyright_pub.author)
            if marc_pub.author and copyright_pub.author
            else 0
        )

        # Calculate publisher score - use different strategies for renewal vs registration
        if marc_pub.publisher:
            if copyright_pub.source == "Renewal" and copyright_pub.full_text:
                # For renewals: fuzzy match MARC publisher against renewal full_text
                publisher_score = fuzz.partial_ratio(marc_pub.publisher, copyright_pub.full_text)
            elif copyright_pub.publisher:
                # For registrations: direct publisher comparison
                publisher_score = fuzz.ratio(marc_pub.publisher, copyright_pub.publisher)
            else:
                publisher_score = 0
        else:
            publisher_score = 0

        # Dynamic weighted scoring based on generic title detection
        # Check if either title is generic (MARC or copyright record)
        marc_title_is_generic = False
        copyright_title_is_generic = False

        if generic_detector:
            marc_title_is_generic = generic_detector.is_generic(
                marc_pub.original_title, marc_pub.language_code
            )
            copyright_title_is_generic = generic_detector.is_generic(
                copyright_pub.original_title, copyright_pub.language_code
            )

        # Determine if any title is generic
        has_generic_title = marc_title_is_generic or copyright_title_is_generic

        # Apply dynamic scoring weights
        if marc_pub.publisher and (copyright_pub.publisher or copyright_pub.full_text):
            if has_generic_title:
                # Generic title detected: title=30%, author=45%, publisher=25%
                combined_score = (
                    (title_score * 0.3) + (author_score * 0.45) + (publisher_score * 0.25)
                )
            else:
                # Normal scoring: title=60%, author=25%, publisher=15%
                combined_score = (
                    (title_score * 0.6) + (author_score * 0.25) + (publisher_score * 0.15)
                )
        else:
            if has_generic_title:
                # Generic title, no publisher: title=40%, author=60%
                combined_score = (title_score * 0.4) + (author_score * 0.6)
            else:
                # Normal, no publisher: title=70%, author=30%
                combined_score = (title_score * 0.7) + (author_score * 0.3)

        # Apply thresholds: publisher threshold only matters if MARC has publisher data
        publisher_threshold_met = not marc_pub.publisher or publisher_score >= publisher_threshold

        if (
            combined_score > best_score
            and (
                not marc_pub.author or not copyright_pub.author or author_score >= author_threshold
            )
            and publisher_threshold_met
        ):

            best_score = combined_score
            best_match = {
                "marc_record": marc_pub.to_dict(),
                "copyright_record": copyright_pub.to_dict(),
                "similarity_scores": {
                    "title": title_score,
                    "author": author_score,
                    "publisher": publisher_score,
                    "combined": combined_score,
                },
                "generic_title_info": {
                    "marc_title_is_generic": marc_title_is_generic,
                    "copyright_title_is_generic": copyright_title_is_generic,
                    "has_generic_title": has_generic_title,
                    "marc_detection_reason": (
                        generic_detector.get_detection_reason(
                            marc_pub.original_title, marc_pub.language_code
                        )
                        if generic_detector
                        else "none"
                    ),
                    "copyright_detection_reason": (
                        generic_detector.get_detection_reason(
                            copyright_pub.original_title, copyright_pub.language_code
                        )
                        if generic_detector
                        else "none"
                    ),
                },
            }

            # Early termination: Only exit if we have BOTH title and author with very high confidence
            if (
                title_score >= early_exit_title
                and marc_pub.author
                and copyright_pub.author
                and author_score >= early_exit_author
            ):
                break

    return best_match


# find_best_metaphone_match function removed to reduce false positives


def save_matches_csv(marc_publications: List[Publication], csv_file: str):
    """Save results to CSV file with country and status information"""
    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        csv_writer = writer(f)
        csv_writer.writerow(
            [
                "MARC ID",
                "MARC Title",
                "MARC Author",
                "MARC Year",
                "MARC Publisher",
                "MARC Place",
                "MARC Edition",
                "Language Code",
                "Country Code",
                "Country Classification",
                "Copyright Status",
                "Generic Title Detected",
                "Generic Detection Reason",
                "Registration Generic Title",
                "Renewal Generic Title",
                "Registration Source ID",
                "Renewal Entry ID",
                "Registration Title",
                "Registration Author",
                "Registration Publisher",
                "Registration Date",
                "Registration Similarity Score",
                "Registration Title Score",
                "Registration Author Score",
                "Registration Publisher Score",
                "Renewal Title",
                "Renewal Author",
                "Renewal Publisher",
                "Renewal Date",
                "Renewal Similarity Score",
                "Renewal Title Score",
                "Renewal Author Score",
                "Renewal Publisher Score",
            ]
        )

        for pub in marc_publications:
            # Get single match data for registration
            reg_source_id = pub.registration_match.source_id if pub.registration_match else ""
            reg_title = pub.registration_match.matched_title if pub.registration_match else ""
            reg_author = pub.registration_match.matched_author if pub.registration_match else ""
            reg_date = pub.registration_match.matched_date if pub.registration_match else ""
            reg_similarity_score = (
                f"{pub.registration_match.similarity_score:.1f}" if pub.registration_match else ""
            )
            reg_title_score = (
                f"{pub.registration_match.title_score:.1f}" if pub.registration_match else ""
            )
            reg_author_score = (
                f"{pub.registration_match.author_score:.1f}" if pub.registration_match else ""
            )
            reg_publisher = (
                pub.registration_match.matched_publisher if pub.registration_match else ""
            )
            reg_publisher_score = (
                f"{pub.registration_match.publisher_score:.1f}" if pub.registration_match else ""
            )

            # Get single match data for renewal
            ren_entry_id = pub.renewal_match.source_id if pub.renewal_match else ""
            ren_title = pub.renewal_match.matched_title if pub.renewal_match else ""
            ren_author = pub.renewal_match.matched_author if pub.renewal_match else ""
            ren_date = pub.renewal_match.matched_date if pub.renewal_match else ""
            ren_similarity_score = (
                f"{pub.renewal_match.similarity_score:.1f}" if pub.renewal_match else ""
            )
            ren_title_score = f"{pub.renewal_match.title_score:.1f}" if pub.renewal_match else ""
            ren_author_score = f"{pub.renewal_match.author_score:.1f}" if pub.renewal_match else ""

            # Get renewal publisher data
            ren_publisher = pub.renewal_match.matched_publisher if pub.renewal_match else ""
            ren_publisher_score = (
                f"{pub.renewal_match.publisher_score:.1f}" if pub.renewal_match else ""
            )

            csv_writer.writerow(
                [
                    pub.source_id,
                    pub.original_title,
                    pub.original_author,
                    pub.year,
                    pub.original_publisher,
                    pub.original_place,
                    pub.original_edition,
                    pub.language_code,
                    pub.country_code,
                    pub.country_classification.value,
                    pub.copyright_status.value,
                    pub.generic_title_detected,
                    pub.generic_detection_reason,
                    pub.registration_generic_title,
                    pub.renewal_generic_title,
                    reg_source_id,
                    ren_entry_id,
                    reg_title,
                    reg_author,
                    reg_publisher,
                    reg_date,
                    reg_similarity_score,
                    reg_title_score,
                    reg_author_score,
                    reg_publisher_score,
                    ren_title,
                    ren_author,
                    ren_publisher,
                    ren_date,
                    ren_similarity_score,
                    ren_title_score,
                    ren_author_score,
                    ren_publisher_score,
                ]
            )
