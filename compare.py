"""
MARC Publication Data Comparison Tool

Command-line application for comparing MARC publication data
with copyright registry entries to identify potential matches.
"""

# Standard library imports
from argparse import ArgumentParser
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures import as_completed
from datetime import datetime
from logging import DEBUG
from logging import FileHandler
from logging import Formatter
from logging import INFO
from logging import StreamHandler
from logging import getLogger
from multiprocessing import cpu_count
from os import rmdir
from os import unlink
from os.path import join
from pickle import dump
from tempfile import mkdtemp
from time import time

# Local imports
from marc_pd_tool import CopyrightDataLoader
from marc_pd_tool import ParallelMarcExtractor
from marc_pd_tool import RenewalDataLoader
from marc_pd_tool import process_batch
from marc_pd_tool import save_matches_csv
from marc_pd_tool.indexer import build_index


def setup_logging(log_file: str = None, debug: bool = False):
    """Configure logging to console and optionally to file"""
    # Remove any existing handlers
    root_logger = getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Set log level based on debug flag
    log_level = DEBUG if debug else INFO

    # Create formatter
    formatter_str = "%(asctime)s - %(levelname)s - %(message)s"

    # Always add console handler
    console_handler = StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(Formatter(formatter_str))
    root_logger.addHandler(console_handler)

    # Add file handler if specified
    if log_file:
        file_handler = FileHandler(log_file)
        file_handler.setLevel(log_level)
        file_handler.setFormatter(Formatter(formatter_str))
        root_logger.addHandler(file_handler)

    root_logger.setLevel(log_level)


logger = getLogger(__name__)


def format_time_duration(seconds: float) -> str:
    """Format time duration in human-readable format (days, hours, minutes, seconds)"""
    total_seconds = int(seconds)
    days = total_seconds // (24 * 3600)
    hours = (total_seconds % (24 * 3600)) // 3600
    minutes = (total_seconds % 3600) // 60

    if days > 0:
        return f"{days}d {hours}h {minutes}m"
    elif hours > 0:
        return f"{hours}h {minutes}m"
    elif minutes > 0:
        return f"{minutes}m"
    else:
        return f"{total_seconds}s"


def main():
    parser = ArgumentParser(
        description="MARC data comparison with registration and renewal matching"
    )
    parser.add_argument(
        "--marcxml", required=True, help="Path to MARC XML file or directory of MARC files"
    )
    parser.add_argument(
        "--copyright-dir", required=True, help="Path to copyright registration XML directory"
    )
    parser.add_argument("--renewal-dir", required=True, help="Path to renewal TSV directory")
    parser.add_argument("--output", "-o", default="matches.csv", help="Output CSV file")
    parser.add_argument("--batch-size", type=int, default=500, help="MARC records per batch")
    parser.add_argument(
        "--max-workers", type=int, default=None, help="Number of processes (default: CPU count)"
    )
    parser.add_argument("--title-threshold", type=int, default=80)
    parser.add_argument("--author-threshold", type=int, default=70)
    parser.add_argument("--year-tolerance", type=int, default=2)
    parser.add_argument(
        "--early-exit-title",
        type=int,
        default=95,
        help="Title score for early termination (default: 95)",
    )
    parser.add_argument(
        "--early-exit-author",
        type=int,
        default=90,
        help="Author score for early termination (default: 90)",
    )
    parser.add_argument(
        "--min-year",
        type=int,
        default=None,
        help="Minimum publication year to include (default: current year - 95)",
    )
    parser.add_argument(
        "--max-year",
        type=int,
        default=None,
        help="Maximum publication year to include (default: no limit)",
    )
    parser.add_argument(
        "--log-file",
        type=str,
        default=None,
        help="Write logs to specified file (default: console only)",
    )
    parser.add_argument(
        "--debug", action="store_true", help="Enable DEBUG level logging for verbose details"
    )

    args = parser.parse_args()

    # Set minimum year if not provided
    if args.min_year is None:
        current_year = datetime.now().year
        args.min_year = current_year - 95

    # Validate year range
    if args.max_year is not None and args.max_year < args.min_year:
        raise ValueError(
            f"Max year ({args.max_year}) cannot be less than min year ({args.min_year})"
        )

    # Set number of workers
    if args.max_workers is None:
        args.max_workers = cpu_count()

    # Configure logging
    setup_logging(args.log_file, args.debug)

    start_time = time()
    logger.info("=== STARTING PUBLICATION COMPARISON ===")
    logger.info(f"Configuration: {args.max_workers} workers, batch_size={args.batch_size}")
    logger.info(
        f"Thresholds: title={args.title_threshold}, author={args.author_threshold}, year_tolerance={args.year_tolerance}"
    )
    if args.max_year is not None:
        logger.info(f"Publication year range: {args.min_year} - {args.max_year}")
    else:
        logger.info(f"Minimum publication year: {args.min_year} (no maximum)")

    # Phase 1: Extract all MARC records into batches
    logger.info("=== PHASE 1: EXTRACTING MARC RECORDS ===")
    marc_extractor = ParallelMarcExtractor(
        args.marcxml, args.batch_size, args.min_year, args.max_year
    )
    marc_batches = marc_extractor.extract_all_batches()

    if not marc_batches:
        logger.error("No MARC batches extracted. Exiting.")
        return

    # Phase 2: Load copyright registration data
    logger.info("=== PHASE 2: LOADING COPYRIGHT REGISTRATION DATA ===")
    copyright_loader = CopyrightDataLoader(args.copyright_dir)
    registration_publications = copyright_loader.load_all_copyright_data()

    if not registration_publications:
        logger.error("No copyright registration data loaded. Exiting.")
        return

    # Phase 3: Load renewal data
    logger.info("=== PHASE 3: LOADING RENEWAL DATA ===")
    renewal_loader = RenewalDataLoader(args.renewal_dir)
    renewal_publications = renewal_loader.load_all_renewal_data()

    if not renewal_publications:
        logger.error("No renewal data loaded. Exiting.")
        return

    # Phase 3.5: Build indexes once and serialize to temp files
    logger.info("=== PHASE 3.5: BUILDING AND SERIALIZING INDEXES ===")
    logger.info("Building registration index...")
    registration_index = build_index(registration_publications)
    logger.info("Building renewal index...")
    renewal_index = build_index(renewal_publications)

    # Create temporary files for serialized indexes
    temp_dir = mkdtemp(prefix="marc_indexes_")
    registration_index_file = join(temp_dir, "registration_index.pkl")
    renewal_index_file = join(temp_dir, "renewal_index.pkl")

    logger.info(f"Serializing indexes to temporary files: {temp_dir}")
    with open(registration_index_file, "wb") as f:
        dump(registration_index, f)
    with open(renewal_index_file, "wb") as f:
        dump(renewal_index, f)

    reg_stats = registration_index.get_stats()
    ren_stats = renewal_index.get_stats()
    logger.info(
        f"Registration index: {reg_stats['title_keys']} title keys, {reg_stats['author_keys']} author keys"
    )
    logger.info(
        f"Renewal index: {ren_stats['title_keys']} title keys, {ren_stats['author_keys']} author keys"
    )

    # Phase 4: Process batches in parallel with pre-built indexes
    logger.info("=== PHASE 4: PARALLEL BATCH PROCESSING ===")
    total_marc_records = sum(len(batch) for batch in marc_batches)
    logger.info(
        f"Processing {total_marc_records:,} MARC records in {len(marc_batches)} batches using {args.max_workers} CPU cores"
    )
    logger.info(f"Registration data: {len(registration_publications):,} entries")
    logger.info(f"Renewal data: {len(renewal_publications):,} entries")

    # Prepare batch information for workers (now with pre-built index file paths)
    batch_infos = []
    total_batches = len(marc_batches)
    for i, batch in enumerate(marc_batches):
        batch_info = (
            i + 1,
            batch,
            registration_index_file,
            renewal_index_file,
            total_batches,
            args.title_threshold,
            args.author_threshold,
            args.year_tolerance,
            args.early_exit_title,
            args.early_exit_author,
        )
        batch_infos.append(batch_info)

    all_processed_marc = []
    all_stats = []
    completed_batches = 0
    total_reg_matches = 0
    total_ren_matches = 0

    # Process batches in parallel
    try:
        with ProcessPoolExecutor(max_workers=args.max_workers) as executor:
            # Submit all jobs
            future_to_batch = {
                executor.submit(process_batch, batch_info): batch_info[0]
                for batch_info in batch_infos
            }

            # Collect results as they complete
            for future in as_completed(future_to_batch):
                batch_id = future_to_batch[future]
                try:
                    batch_id_result, processed_marc_batch, batch_stats = future.result()
                    all_processed_marc.extend(processed_marc_batch)
                    all_stats.append(batch_stats)
                    completed_batches += 1

                    elapsed = time() - start_time
                    eta = (elapsed / completed_batches) * (len(marc_batches) - completed_batches)
                    eta_str = format_time_duration(eta)

                    reg_matches = batch_stats["registration_matches_found"]
                    ren_matches = batch_stats["renewal_matches_found"]
                    total_reg_matches += reg_matches
                    total_ren_matches += ren_matches
                    logger.info(
                        f"Completed batch {batch_id}: {reg_matches} registration, {ren_matches} renewal matches "
                        f"(Total: {total_reg_matches} reg, {total_ren_matches} ren) | "
                        f"Progress: {completed_batches}/{len(marc_batches)} | "
                        f"ETA: {eta_str}"
                    )

                except Exception as e:
                    logger.error(f"Batch {batch_id} failed: {e}")
    finally:
        # Clean up temporary index files
        logger.info("Cleaning up temporary index files...")
        try:
            unlink(registration_index_file)
            unlink(renewal_index_file)
            rmdir(temp_dir)
            logger.info("Temporary files cleaned up successfully")
        except Exception as e:
            logger.warning(f"Failed to clean up temporary files: {e}")

    # Phase 5: Save results
    logger.info("=== PHASE 5: SAVING RESULTS ===")
    save_matches_csv(all_processed_marc, args.output)

    # Final summary
    total_time = time() - start_time
    total_marc = sum(stat["marc_count"] for stat in all_stats)
    total_registration_matches = sum(stat["registration_matches_found"] for stat in all_stats)
    total_renewal_matches = sum(stat["renewal_matches_found"] for stat in all_stats)
    total_comparisons = sum(stat["total_comparisons"] for stat in all_stats)
    total_us = sum(stat["us_records"] for stat in all_stats)
    total_non_us = sum(stat["non_us_records"] for stat in all_stats)
    total_unknown = sum(stat["unknown_country_records"] for stat in all_stats)

    # Count copyright status classifications
    status_counts = {}
    for pub in all_processed_marc:
        status = pub.copyright_status.value
        status_counts[status] = status_counts.get(status, 0) + 1

    logger.info("=== FINAL SUMMARY ===")
    print(f"\n{'='*80}")
    print(f"COMPARISON COMPLETE")
    print(f"{'='*80}")
    print(f"MARC records processed: {total_marc:,}")
    print(f"Registration matches found: {total_registration_matches:,}")
    print(f"Renewal matches found: {total_renewal_matches:,}")
    print(f"Total comparisons made: {total_comparisons:,}")
    print(f"")
    print(f"Country Classification:")
    print(f"  US records: {total_us:,} ({total_us/total_marc*100:.1f}%)")
    print(f"  Non-US records: {total_non_us:,} ({total_non_us/total_marc*100:.1f}%)")
    print(f"  Unknown country: {total_unknown:,} ({total_unknown/total_marc*100:.1f}%)")
    print(f"")
    print(f"Copyright Status Results:")
    for status, count in status_counts.items():
        print(f"  {status}: {count:,} ({count/total_marc*100:.1f}%)")
    print(f"")
    print(f"Performance:")
    print(f"  Workers used: {args.max_workers}")
    print(f"  Total time: {format_time_duration(total_time)}")
    print(f"  Speed: {total_marc/(total_time/60):.0f} records/minute")
    print(f"  Output: {args.output}")
    print(f"{'='*80}")


if __name__ == "__main__":
    main()
