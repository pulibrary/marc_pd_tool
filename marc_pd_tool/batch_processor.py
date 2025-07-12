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
from marc_pd_tool.publication import Publication


logger = logging.getLogger(__name__)


def process_batch(
    batch_info: Tuple[int, List[Publication], List[Publication], int, int, int],
) -> Tuple[int, List[Dict], Dict]:
    """
    Process a single batch of MARC records against copyright data.
    This function runs in a separate process.
    """
    batch_id, marc_batch, copyright_publications, title_threshold, author_threshold, year_tolerance = batch_info

    # Set up logging for this process
    process_logger = logging.getLogger(f"batch_{batch_id}")

    matches = []
    stats = {
        "batch_id": batch_id,
        "marc_count": len(marc_batch),
        "matches_found": 0,
        "comparisons_made": 0,
        "copyright_entries_checked": 0,
    }

    process_logger.info(
        f"Process {os.getpid()} starting batch {batch_id} with {len(marc_batch)} MARC records"
    )

    # Filter copyright data by year for this batch (if years are available)
    relevant_copyright = []
    batch_years = set()

    # Collect years from MARC batch
    for pub in marc_batch:
        if pub.year:
            for offset in range(-year_tolerance, year_tolerance + 1):
                batch_years.add(pub.year + offset)

    # Filter copyright publications by year if we have year info
    if batch_years:
        for copyright_pub in copyright_publications:
            if copyright_pub.year and copyright_pub.year in batch_years:
                relevant_copyright.append(copyright_pub)
    else:
        # No year filtering possible, use all copyright data
        relevant_copyright = copyright_publications

    stats["copyright_entries_checked"] = len(relevant_copyright)
    if batch_years:
        process_logger.info(
            f"Batch {batch_id}: Comparing against {len(relevant_copyright):,} copyright entries (year filtered)"
        )
    else:
        process_logger.info(
            f"Batch {batch_id}: Comparing against {len(relevant_copyright):,} copyright entries (no year filtering)"
        )

    # Process each MARC record in the batch
    for i, marc_pub in enumerate(marc_batch):
        if i % 100 == 0 and i > 0:
            process_logger.info(
                f"Batch {batch_id}: Processed {i}/{len(marc_batch)} records, found {len(matches)} matches"
            )

        best_match = find_best_match(
            marc_pub, relevant_copyright, title_threshold, author_threshold, year_tolerance
        )
        if best_match:
            matches.append(best_match)
            stats["matches_found"] += 1

        stats["comparisons_made"] += len(relevant_copyright)

    process_logger.info(
        f"Batch {batch_id} complete: {stats['matches_found']} matches from {stats['marc_count']} records"
    )
    return batch_id, matches, stats


def find_best_match(
    marc_pub: Publication,
    copyright_pubs: List[Publication],
    title_threshold: int,
    author_threshold: int,
    year_tolerance: int,
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

    return best_match


def save_matches_csv(matches: List[Dict], csv_file: str):
    """Save matches to CSV file"""
    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "MARC_ID",
                "MARC_Title",
                "MARC_Author",
                "MARC_Year",
                "MARC_Publisher",
                "Copyright_ID",
                "Copyright_Title",
                "Copyright_Author",
                "Copyright_Year",
                "Copyright_Publisher",
                "Title_Score",
                "Author_Score",
                "Combined_Score",
            ]
        )

        for match in matches:
            marc = match["marc_record"]
            copyright = match["copyright_record"]
            scores = match["similarity_scores"]

            writer.writerow(
                [
                    marc["source_id"],
                    marc["title"],
                    marc["author"],
                    marc["year"],
                    marc["publisher"],
                    copyright["source_id"],
                    copyright["title"],
                    copyright["author"],
                    copyright["year"],
                    copyright["publisher"],
                    scores["title"],
                    scores["author"],
                    scores["combined"],
                ]
            )
