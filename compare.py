#!/usr/bin/env python3
"""
MARC Publication Data Comparison Tool

Command-line application for comparing MARC publication data
with copyright registry entries to identify potential matches.
"""

# Standard library imports
import argparse
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures import as_completed
from datetime import datetime
import logging
import multiprocessing as mp
import time

# Local imports
from marc_pd_tool import CopyrightDataLoader
from marc_pd_tool import ParallelMarcExtractor
from marc_pd_tool import Publication
from marc_pd_tool import process_batch
from marc_pd_tool import save_matches_csv

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Parallel batch-based publication comparison")
    parser.add_argument(
        "--marcxml", required=True, help="Path to MARC XML file or directory of MARC files"
    )
    parser.add_argument("--copyright-dir", required=True, help="Path to copyright XML directory")
    parser.add_argument("--output", "-o", default="matches.csv", help="Output CSV file")
    parser.add_argument("--batch-size", type=int, default=500, help="MARC records per batch")
    parser.add_argument(
        "--max-workers", type=int, default=None, help="Number of processes (default: CPU count)"
    )
    parser.add_argument("--title-threshold", type=int, default=80)
    parser.add_argument("--author-threshold", type=int, default=70)
    parser.add_argument("--year-tolerance", type=int, default=2)
    parser.add_argument(
        "--min-year",
        type=int,
        default=None,
        help="Minimum publication year to include (default: current year - 95)",
    )

    args = parser.parse_args()

    # Set minimum year if not provided
    if args.min_year is None:
        current_year = datetime.now().year
        args.min_year = current_year - 95

    # Set number of workers
    if args.max_workers is None:
        args.max_workers = mp.cpu_count()

    start_time = time.time()
    logger.info("=== STARTING PARALLEL PUBLICATION COMPARISON ===")
    logger.info(f"Configuration: {args.max_workers} workers, batch_size={args.batch_size}")
    logger.info(
        f"Thresholds: title={args.title_threshold}, author={args.author_threshold}, year_tolerance={args.year_tolerance}"
    )
    logger.info(f"Minimum publication year: {args.min_year}")

    # Phase 1: Extract all MARC records into batches
    logger.info("=== PHASE 1: EXTRACTING MARC RECORDS ===")
    marc_extractor = ParallelMarcExtractor(args.marcxml, args.batch_size, args.min_year)
    marc_batches = marc_extractor.extract_all_batches()

    if not marc_batches:
        logger.error("No MARC batches extracted. Exiting.")
        return

    # Phase 2: Load all copyright data
    logger.info("=== PHASE 2: LOADING COPYRIGHT DATA ===")
    copyright_loader = CopyrightDataLoader(args.copyright_dir)
    copyright_publications = copyright_loader.load_all_copyright_data()

    if not copyright_publications:
        logger.error("No copyright data loaded. Exiting.")
        return

    # Phase 3: Process batches in parallel
    logger.info("=== PHASE 3: PARALLEL BATCH PROCESSING ===")
    total_marc_records = sum(len(batch) for batch in marc_batches)
    logger.info(f"Processing {total_marc_records:,} MARC records in {len(marc_batches)} batches using {args.max_workers} CPU cores")

    # Prepare batch information for workers
    batch_infos = []
    for i, batch in enumerate(marc_batches):
        batch_info = (
            i + 1,
            batch,
            copyright_publications,
            args.title_threshold,
            args.author_threshold,
            args.year_tolerance,
        )
        batch_infos.append(batch_info)

    all_matches = []
    all_stats = []
    completed_batches = 0

    # Process batches in parallel
    with ProcessPoolExecutor(max_workers=args.max_workers) as executor:
        # Submit all jobs
        future_to_batch = {
            executor.submit(process_batch, batch_info): batch_info[0] for batch_info in batch_infos
        }

        # Collect results as they complete
        for future in as_completed(future_to_batch):
            batch_id = future_to_batch[future]
            try:
                batch_id_result, batch_matches, batch_stats = future.result()
                all_matches.extend(batch_matches)
                all_stats.append(batch_stats)
                completed_batches += 1

                elapsed = time.time() - start_time
                eta = (elapsed / completed_batches) * (len(marc_batches) - completed_batches)
                
                # Format ETA in a human-readable way
                eta_seconds = int(eta)
                eta_days = eta_seconds // (24 * 3600)
                eta_hours = (eta_seconds % (24 * 3600)) // 3600
                eta_minutes = (eta_seconds % 3600) // 60
                
                if eta_days > 0:
                    eta_str = f"{eta_days}d {eta_hours}h {eta_minutes}m"
                elif eta_hours > 0:
                    eta_str = f"{eta_hours}h {eta_minutes}m"
                else:
                    eta_str = f"{eta_minutes}m"

                logger.info(
                    f"Completed batch {batch_id}: {batch_stats['matches_found']} matches | "
                    f"Progress: {completed_batches}/{len(marc_batches)} | "
                    f"Total matches: {len(all_matches):,} | "
                    f"ETA: {eta_str}"
                )

            except Exception as e:
                logger.error(f"Batch {batch_id} failed: {e}")

    # Phase 4: Save results
    logger.info("=== PHASE 4: SAVING RESULTS ===")
    save_matches_csv(all_matches, args.output)

    # Final summary
    total_time = time.time() - start_time
    total_marc = sum(stat["marc_count"] for stat in all_stats)
    total_comparisons = sum(stat["comparisons_made"] for stat in all_stats)

    logger.info("=== FINAL SUMMARY ===")
    print(f"\n{'='*60}")
    print(f"COMPARISON COMPLETE")
    print(f"{'='*60}")
    print(f"MARC records processed: {total_marc:,}")
    print(f"Matches found: {len(all_matches):,}")
    print(f"Match rate: {len(all_matches)/total_marc*100:.2f}%")
    print(f"Total comparisons: {total_comparisons:,}")
    print(f"Workers used: {args.max_workers}")
    print(f"Total time: {total_time/60:.1f} minutes")
    print(f"Speed: {total_marc/(total_time/60):.0f} records/minute")
    print(f"Output: {args.output}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
