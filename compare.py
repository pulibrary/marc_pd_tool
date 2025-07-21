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
from os.path import abspath
from os.path import dirname
from os.path import join
from time import time

# Local imports
from marc_pd_tool import CopyrightDataLoader
from marc_pd_tool import ParallelMarcExtractor
from marc_pd_tool import RenewalDataLoader
from marc_pd_tool.cache_manager import CacheManager
from marc_pd_tool.config_loader import ConfigLoader
from marc_pd_tool.csv_exporter import save_matches_csv
from marc_pd_tool.generic_title_detector import GenericTitleDetector
from marc_pd_tool.indexer import build_index
from marc_pd_tool.matching_engine import process_batch


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


def build_year_part(min_year, max_year):
    """Build year component for dynamic filename"""
    if min_year is not None and max_year is not None:
        if min_year == max_year:
            return f"{min_year}-only"
        else:
            return f"{min_year}-{max_year}"
    elif min_year is not None:
        return f"after-{min_year}"
    elif max_year is not None:
        return f"before-{max_year}"
    return None


def generate_output_filename(args):
    """Generate dynamic output filename based on filtering parameters"""
    # If user specified custom output, use it unchanged
    if args.output != "matches.csv":  # Not using default
        return args.output

    # Build dynamic filename from filters
    parts = ["matches"]

    # Add country filter
    if args.us_only:
        parts.append("us-only")

    # Add year filter
    if args.min_year is not None or args.max_year is not None:
        year_part = build_year_part(args.min_year, args.max_year)
        if year_part:
            parts.append(year_part)

    return "_".join(parts) + ".csv"


def main():
    cwd = dirname(abspath(__file__))

    # First pass: parse only config argument to load configuration
    config_parser = ArgumentParser(add_help=False)
    config_parser.add_argument("--config", type=str, default=None)
    config_args, _ = config_parser.parse_known_args()

    # Load configuration to set defaults
    config_loader = ConfigLoader(config_args.config)

    # Main parser with configuration-based defaults
    parser = ArgumentParser(
        description="MARC data comparison with registration and renewal matching"
    )
    parser.add_argument(
        "--marcxml", required=True, help="Path to MARC XML file or directory of MARC files"
    )
    parser.add_argument(
        "--copyright-dir",
        default=f"{cwd}/nypl-reg/xml",
        help="Path to copyright registration XML directory",
    )
    parser.add_argument(
        "--renewal-dir", default=f"{cwd}/nypl-ren/data", help="Path to renewal TSV directory"
    )
    parser.add_argument(
        "--output",
        "-o",
        default="matches.csv",
        help="Output CSV file (default auto-generates descriptive names based on filters)",
    )
    parser.add_argument("--batch-size", type=int, default=200, help="MARC records per batch")
    parser.add_argument(
        "--max-workers", type=int, default=None, help="Number of processes (default: CPU count - 2)"
    )
    parser.add_argument("--title-threshold", type=int, default=config_loader.get_threshold("title"))
    parser.add_argument(
        "--author-threshold", type=int, default=config_loader.get_threshold("author")
    )
    parser.add_argument(
        "--year-tolerance", type=int, default=config_loader.get_threshold("year_tolerance")
    )
    parser.add_argument(
        "--early-exit-title",
        type=int,
        default=config_loader.get_threshold("early_exit_title"),
        help="Title score for early termination (default: from config)",
    )
    parser.add_argument(
        "--early-exit-author",
        type=int,
        default=config_loader.get_threshold("early_exit_author"),
        help="Author score for early termination (default: from config)",
    )
    parser.add_argument(
        "--min-year",
        type=int,
        default=None,
        help="Minimum publication year to include (default: current year - 96)",
    )
    parser.add_argument(
        "--max-year",
        type=int,
        default=None,
        help="Maximum publication year to include (default: no limit)",
    )
    parser.add_argument(
        "--us-only",
        action="store_true",
        help="Only process records from US publications (significantly faster for US-focused research)",
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
    parser.add_argument(
        "--generic-title-threshold",
        type=int,
        default=config_loader.get_generic_detector_config()["frequency_threshold"],
        help="Minimum occurrences for a title to be considered generic (default: from config)",
    )
    parser.add_argument(
        "--disable-generic-detection",
        action="store_true",
        help="Disable generic title detection and use normal scoring for all titles",
    )
    parser.add_argument(
        "--single-file",
        action="store_true",
        help="Save all results to a single file instead of separate files by copyright status",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to JSON configuration file for scoring weights, thresholds, and word lists",
    )
    parser.add_argument(
        "--cache-dir",
        type=str,
        default=".marcpd_cache",
        help="Directory for persistent data cache (default: .marcpd_cache)",
    )
    parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Force refresh of all cached data (bypass cache)",
    )
    parser.add_argument(
        "--no-cache", action="store_true", help="Disable caching entirely (useful for one-off runs)"
    )

    args = parser.parse_args()

    # Set minimum year if not provided
    if args.min_year is None:
        current_year = datetime.now().year
        args.min_year = current_year - 96

    # Validate year range
    if args.max_year is not None and args.max_year < args.min_year:
        raise ValueError(
            f"Max year ({args.max_year}) cannot be less than min year ({args.min_year})"
        )

    # Set number of workers
    if args.max_workers is None:
        args.max_workers = max(1, cpu_count() - 2)  # Use all cores minus 2, minimum 1

    # Configure logging
    setup_logging(args.log_file, args.debug)

    # Initialize cache manager
    if not args.no_cache:
        cache_manager = CacheManager(args.cache_dir)
        if args.force_refresh:
            logger.info("Force refresh requested - clearing all caches")
            cache_manager.clear_all_caches()
    else:
        cache_manager = None
        logger.info("Caching disabled via --no-cache flag")

    start_time = time()
    logger.info("=== STARTING PUBLICATION COMPARISON ===")
    logger.info(f"Configuration: {args.max_workers} workers, batch_size={args.batch_size}")
    logger.info(
        f"Thresholds: title={args.title_threshold}, author={args.author_threshold}, year_tolerance={args.year_tolerance}"
    )
    if args.disable_generic_detection:
        logger.info("Generic title detection: DISABLED")
    else:
        logger.info(
            f"Generic title detection: ENABLED (frequency threshold: {args.generic_title_threshold})"
        )
    if args.max_year is not None:
        logger.info(f"Publication year range: {args.min_year} - {args.max_year}")
    else:
        logger.info(f"Minimum publication year: {args.min_year} (no maximum)")

    if args.us_only:
        logger.info("Country filter: US publications only (non-US records will be excluded)")

    # Log cache information
    if cache_manager:
        logger.info(f"Cache directory: {args.cache_dir}")
        cache_info = cache_manager.get_cache_info()
        cached_components = [
            name for name, info in cache_info["components"].items() if info["cached"]
        ]
        if cached_components:
            logger.info(f"Cached components available: {', '.join(cached_components)}")
        else:
            logger.info("No cached components available - will build cache during run")

    # Phase 1: Extract all MARC records into batches
    logger.info("=== PHASE 1: EXTRACTING MARC RECORDS ===")
    marc_extractor = ParallelMarcExtractor(
        args.marcxml, args.batch_size, args.min_year, args.max_year, args.us_only
    )
    marc_batches = marc_extractor.extract_all_batches()

    if not marc_batches:
        logger.error("No MARC batches extracted. Exiting.")
        return

    # Phase 2: Load copyright registration data
    logger.info("=== PHASE 2: LOADING COPYRIGHT REGISTRATION DATA ===")

    # Try to load from cache first
    registration_publications = None
    if cache_manager and not args.force_refresh:
        registration_publications = cache_manager.get_cached_copyright_data(args.copyright_dir)

    if registration_publications is None:
        # Load from source files
        logger.info("Loading copyright registration data from source files...")
        copyright_loader = CopyrightDataLoader(args.copyright_dir)
        registration_publications = copyright_loader.load_all_copyright_data()

        # Cache the loaded data
        if cache_manager and registration_publications:
            cache_manager.cache_copyright_data(args.copyright_dir, registration_publications)
    else:
        logger.info(f"Loaded {len(registration_publications):,} copyright publications from cache")

    if not registration_publications:
        logger.error("No copyright registration data loaded. Exiting.")
        return

    # Phase 3: Load renewal data
    logger.info("=== PHASE 3: LOADING RENEWAL DATA ===")

    # Try to load from cache first
    renewal_publications = None
    if cache_manager and not args.force_refresh:
        renewal_publications = cache_manager.get_cached_renewal_data(args.renewal_dir)

    if renewal_publications is None:
        # Load from source files
        logger.info("Loading renewal data from source files...")
        renewal_loader = RenewalDataLoader(args.renewal_dir)
        renewal_publications = renewal_loader.load_all_renewal_data()

        # Cache the loaded data
        if cache_manager and renewal_publications:
            cache_manager.cache_renewal_data(args.renewal_dir, renewal_publications)
    else:
        logger.info(f"Loaded {len(renewal_publications):,} renewal publications from cache")

    if not renewal_publications:
        logger.error("No renewal data loaded. Exiting.")
        return

    # Phase 3.5: Create and populate generic title detector
    logger.info("=== PHASE 3.5: CREATING GENERIC TITLE DETECTOR ===")
    if args.disable_generic_detection:
        logger.info("Generic title detection disabled via CLI flag")
        generic_detector = None
    else:
        logger.info(
            f"Generic title detection enabled (frequency threshold: {args.generic_title_threshold})"
        )

        # Try to load from cache first
        detector_config = {
            "frequency_threshold": args.generic_title_threshold,
            "disabled": args.disable_generic_detection,
        }

        generic_detector = None
        if cache_manager and not args.force_refresh:
            generic_detector = cache_manager.get_cached_generic_detector(
                args.copyright_dir, args.renewal_dir, detector_config
            )
            if generic_detector is not None:
                logger.info("Loading generic title detector from cache...")

        if generic_detector is None:
            # Create and populate detector from scratch
            logger.info("Building generic title detector from source data...")
            generic_detector = GenericTitleDetector(
                frequency_threshold=args.generic_title_threshold, config=config_loader
            )

            # Populate detector with titles from all datasets for frequency analysis
            logger.info("Populating generic title detector with MARC titles...")
            for batch in marc_batches:
                for pub in batch:
                    generic_detector.add_title(pub.original_title)

            logger.info("Populating generic title detector with registration titles...")
            for pub in registration_publications:
                generic_detector.add_title(pub.original_title)

            logger.info("Populating generic title detector with renewal titles...")
            for pub in renewal_publications:
                generic_detector.add_title(pub.original_title)

            # Cache the populated detector
            if cache_manager:
                cache_manager.cache_generic_detector(
                    args.copyright_dir, args.renewal_dir, detector_config, generic_detector
                )

        detector_stats = generic_detector.get_stats()
        logger.info(
            f"Generic title detector: {detector_stats['total_unique_titles']} unique titles, "
            f"{detector_stats['generic_by_frequency']} generic by frequency (>{detector_stats['frequency_threshold']} occurrences)"
        )

    # Phase 3.6: Build indexes once and serialize to temp files
    logger.info("=== PHASE 3.6: BUILDING AND SERIALIZING INDEXES ===")

    # Create configuration hash for cache validation
    # Standard library imports
    from hashlib import md5

    config_data = {
        "title_threshold": args.title_threshold,
        "author_threshold": args.author_threshold,
        "year_tolerance": args.year_tolerance,
    }
    config_hash = md5(str(config_data).encode()).hexdigest()

    # Try to load indexes from cache first
    cached_indexes = None
    if cache_manager and not args.force_refresh:
        cached_indexes = cache_manager.get_cached_indexes(
            args.copyright_dir, args.renewal_dir, config_hash
        )

    if cached_indexes is not None:
        registration_index, renewal_index = cached_indexes
        logger.info("Loaded indexes from cache")
    else:
        # Build indexes from scratch
        logger.info("Building registration index...")
        registration_index = build_index(registration_publications, config_loader)
        logger.info("Building renewal index...")
        renewal_index = build_index(renewal_publications, config_loader)

        # Cache the built indexes
        if cache_manager:
            cache_manager.cache_indexes(
                args.copyright_dir, args.renewal_dir, config_hash, registration_index, renewal_index
            )

    # Indexes and detector are now available directly from cache for worker processes

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

    # Prepare batch information for workers (now with cache configuration)
    # For --no-cache mode, we need to create a temporary cache for worker processes
    worker_cache_dir = args.cache_dir if cache_manager else None
    if not cache_manager:
        # Create temporary cache for worker processes when --no-cache is used
        # Standard library imports
        from tempfile import mkdtemp

        worker_cache_dir = mkdtemp(prefix="marc_worker_cache_")
        temp_cache_manager = CacheManager(worker_cache_dir)
        # Cache the current indexes and detector for worker processes
        temp_cache_manager.cache_indexes(
            args.copyright_dir, args.renewal_dir, config_hash, registration_index, renewal_index
        )
        if generic_detector is not None:
            temp_cache_manager.cache_generic_detector(
                args.copyright_dir, args.renewal_dir, detector_config, generic_detector
            )

    batch_infos = []
    total_batches = len(marc_batches)
    for i, batch in enumerate(marc_batches):
        batch_info = (
            i + 1,
            batch,
            worker_cache_dir,
            args.copyright_dir,
            args.renewal_dir,
            config_hash,
            detector_config,
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
            future_to_batch = {}
            for batch_info in batch_infos:
                batch_id = batch_info[0]
                future = executor.submit(process_batch, batch_info)
                future_to_batch[future] = batch_id

            logger.info(
                f"Submitted {total_batches} batches for processing with {args.max_workers} workers"
            )

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
        # Clean up temporary worker cache if created for --no-cache mode
        if not cache_manager and worker_cache_dir:
            logger.debug("Cleaning up temporary worker cache...")
            try:
                # Standard library imports
                from shutil import rmtree

                rmtree(worker_cache_dir)
            except Exception as e:
                logger.warning(f"Failed to clean up temporary worker cache: {e}")

    # Phase 5: Save results
    logger.info("=== PHASE 5: SAVING RESULTS ===")
    if args.single_file:
        logger.info("Saving results to single file (legacy mode)")
    else:
        logger.info("Saving results to separate files by copyright status (default mode)")
    output_filename = generate_output_filename(args)
    save_matches_csv(all_processed_marc, output_filename, single_file=args.single_file)

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

    if args.single_file:
        print(f"  Output: {output_filename}")
    else:
        print(f"  Output files (by copyright status):")
        # Import here to avoid circular import
        # Standard library imports
        from os.path import splitext

        base_name, ext = splitext(output_filename)
        for status, count in status_counts.items():
            if count > 0:  # Only show files that actually contain records
                status_filename = status.lower()
                status_file = f"{base_name}_{status_filename}{ext}"
                print(f"    {status_file} ({count:,} records)")

    print(f"{'='*80}")


if __name__ == "__main__":
    main()
