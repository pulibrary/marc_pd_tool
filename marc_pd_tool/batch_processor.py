"""Batch processing functions for parallel publication matching"""

# Standard library imports
import csv
import logging
import os
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple

# Third party imports
from fuzzywuzzy import fuzz

# Local imports
from marc_pd_tool.indexer import build_index
from marc_pd_tool.publication import MatchResult
from marc_pd_tool.publication import Publication

logger = logging.getLogger(__name__)


def process_batch(
    batch_info: Tuple[
        int, List[Publication], List[Publication], List[Publication], int, int, int, int, int
    ],
) -> Tuple[int, List[Publication], Dict]:
    """
    Process a single batch of MARC records against both registration and renewal data.
    This function runs in a separate process.
    """
    (
        batch_id,
        marc_batch,
        registration_pubs,
        renewal_pubs,
        title_threshold,
        author_threshold,
        year_tolerance,
        early_exit_title,
        early_exit_author,
    ) = batch_info

    # Set up logging for this process
    process_logger = logging.getLogger(f"batch_{batch_id}")

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
        f"Process {os.getpid()} starting batch {batch_id} with {len(marc_batch)} MARC records"
    )
    process_logger.info(
        f"Batch {batch_id}: {len(registration_pubs):,} registration entries, {len(renewal_pubs):,} renewal entries"
    )

    # Build indexes for fast candidate lookup
    process_logger.info(f"Batch {batch_id}: Building registration index...")
    registration_index = build_index(registration_pubs)
    process_logger.info(f"Batch {batch_id}: Building renewal index...")
    renewal_index = build_index(renewal_pubs)

    reg_stats = registration_index.get_stats()
    ren_stats = renewal_index.get_stats()
    process_logger.info(
        f"Batch {batch_id}: Registration index - {reg_stats['title_keys']} title keys, {reg_stats['author_keys']} author keys"
    )
    process_logger.info(
        f"Batch {batch_id}: Renewal index - {ren_stats['title_keys']} title keys, {ren_stats['author_keys']} author keys"
    )

    # Process each MARC record in the batch
    for i, marc_pub in enumerate(marc_batch):
        if i % 100 == 0 and i > 0:
            reg_matches = stats["registration_matches_found"]
            ren_matches = stats["renewal_matches_found"]
            process_logger.info(
                f"Batch {batch_id}: Processed {i}/{len(marc_batch)} records, "
                f"found {reg_matches} registration matches, {ren_matches} renewal matches"
            )

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
            early_exit_title,
            early_exit_author,
        )
        if reg_match:
            match_result = MatchResult(
                matched_title=reg_match["copyright_record"]["title"],
                matched_author=reg_match["copyright_record"]["author"],
                similarity_score=reg_match["similarity_scores"]["combined"],
                year_difference=(
                    abs(marc_pub.year - reg_match["copyright_record"]["year"])
                    if marc_pub.year and reg_match["copyright_record"]["year"]
                    else 0
                ),
                source_id=reg_match["copyright_record"]["source_id"],
                source_type="registration",
            )
            marc_pub.add_registration_match(match_result)
            stats["registration_matches_found"] += 1

        # Find renewal candidates using index
        ren_candidates = renewal_index.get_candidates_list(marc_pub, year_tolerance)
        ren_match = find_best_match(
            marc_pub,
            ren_candidates,
            title_threshold,
            author_threshold,
            year_tolerance,
            early_exit_title,
            early_exit_author,
        )
        if ren_match:
            match_result = MatchResult(
                matched_title=ren_match["copyright_record"]["title"],
                matched_author=ren_match["copyright_record"]["author"],
                similarity_score=ren_match["similarity_scores"]["combined"],
                year_difference=(
                    abs(marc_pub.year - ren_match["copyright_record"]["year"])
                    if marc_pub.year and ren_match["copyright_record"]["year"]
                    else 0
                ),
                source_id=ren_match["copyright_record"]["source_id"],
                source_type="renewal",
            )
            marc_pub.add_renewal_match(match_result)
            stats["renewal_matches_found"] += 1

        stats["total_comparisons"] += len(reg_candidates) + len(ren_candidates)

        # Determine copyright status based on matches and country
        marc_pub.determine_copyright_status()

    process_logger.info(
        f"Batch {batch_id} complete: {stats['registration_matches_found']} registration matches, "
        f"{stats['renewal_matches_found']} renewal matches from {stats['marc_count']} records"
    )
    process_logger.info(
        f"Batch {batch_id} country breakdown: {stats['us_records']} US, "
        f"{stats['non_us_records']} Non-US, {stats['unknown_country_records']} Unknown"
    )

    return batch_id, marc_batch, stats


def find_best_match(
    marc_pub: Publication,
    copyright_pubs: List[Publication],
    title_threshold: int,
    author_threshold: int,
    year_tolerance: int,
    early_exit_title: int = 95,
    early_exit_author: int = 90,
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
        combined_score = (title_score * 0.7) + (author_score * 0.3)

        if combined_score > best_score and (
            not marc_pub.author or not copyright_pub.author or author_score >= author_threshold
        ):

            best_score = combined_score
            best_match = {
                "marc_record": marc_pub.to_dict(),
                "copyright_record": copyright_pub.to_dict(),
                "similarity_scores": {
                    "title": title_score,
                    "author": author_score,
                    "combined": combined_score,
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


def save_matches_csv(marc_publications: List[Publication], csv_file: str):
    """Save results to CSV file with country and status information"""
    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "MARC_ID",
                "MARC_Title",
                "MARC_Author",
                "MARC_Year",
                "MARC_Publisher",
                "MARC_Place",
                "Country_Code",
                "Country_Classification",
                "Copyright_Status",
                "Registration_Matches_Count",
                "Renewal_Matches_Count",
                "Registration_Match_Details",
                "Renewal_Match_Details",
            ]
        )

        for pub in marc_publications:
            # Format match details
            reg_details = (
                "; ".join(
                    [
                        f"{match.source_id}({match.similarity_score:.1f})"
                        for match in pub.registration_matches
                    ]
                )
                if pub.registration_matches
                else ""
            )

            ren_details = (
                "; ".join(
                    [
                        f"{match.source_id}({match.similarity_score:.1f})"
                        for match in pub.renewal_matches
                    ]
                )
                if pub.renewal_matches
                else ""
            )

            writer.writerow(
                [
                    pub.source_id,
                    pub.original_title,
                    pub.original_author,
                    pub.year,
                    pub.original_publisher,
                    pub.original_place,
                    pub.country_code,
                    pub.country_classification.value,
                    pub.copyright_status.value,
                    len(pub.registration_matches),
                    len(pub.renewal_matches),
                    reg_details,
                    ren_details,
                ]
            )
