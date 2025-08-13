# marc_pd_tool/adapters/cli/main.py

"""
MARC Publication Data Comparison Tool - CLI Main Module

Command-line interface for comparing MARC publication data
with copyright registry entries to identify potential matches.

This CLI uses the public API provided by marc_pd_tool.
"""

# Standard library imports
from datetime import datetime
from logging import getLogger
from multiprocessing import cpu_count
from os import makedirs
from os.path import dirname
from time import time

# Local imports
from marc_pd_tool import MarcCopyrightAnalyzer
from marc_pd_tool.adapters.cli.logging_setup import log_run_summary
from marc_pd_tool.adapters.cli.logging_setup import set_up_logging
from marc_pd_tool.adapters.cli.parser import create_argument_parser
from marc_pd_tool.adapters.cli.parser import generate_output_filename
from marc_pd_tool.application.models.config_models import AnalysisOptions
from marc_pd_tool.infrastructure import RunIndexManager

logger = getLogger(__name__)


def main() -> None:
    """Main CLI entry point using the public API"""
    parser = create_argument_parser()
    args = parser.parse_args()

    # Log the min_year being used
    if args.min_year is not None:
        logger.info(f"Using min_year filter: {args.min_year}")

    # Validate year range
    if args.max_year is not None and args.min_year is not None and args.max_year < args.min_year:
        raise ValueError(
            f"Max year ({args.max_year}) cannot be less than min year ({args.min_year})"
        )

    # Force single-file output when score-everything mode is enabled
    if args.score_everything:
        args.single_file = True

    # Set number of workers
    if args.max_workers is None or args.max_workers == 0:
        args.max_workers = max(1, cpu_count() - 2)  # Use all cores minus 2, minimum 1

    # Configure logging
    log_file_path = set_up_logging(
        log_file=args.log_file,
        log_level=args.log_level,
        silent=args.silent,
        disable_file_logging=args.disable_file_logging,
    )

    # Record start time
    start_time = time()
    start_time_dt = datetime.now()

    # Initialize run index manager
    run_index_manager = RunIndexManager()
    output_filename = generate_output_filename(args)

    # Create reports directory if it doesn't exist
    output_dir = dirname(output_filename)
    if output_dir:
        makedirs(output_dir, exist_ok=True)

    # Create initial run info
    run_info = {
        "timestamp": start_time_dt.isoformat(),
        "log_file": log_file_path if log_file_path else "",
        "marcxml": args.marcxml,
        "output_file": output_filename,
        "us_only": str(args.us_only),
        "min_year": str(args.min_year) if args.min_year else "",
        "max_year": str(args.max_year) if args.max_year else "",
        "brute_force": str(args.brute_force_missing_year),
        "score_everything_mode": str(args.score_everything),
        "title_threshold": str(args.title_threshold),
        "author_threshold": str(args.author_threshold),
        "marc_count": "",  # Will be updated at the end
        "duration_seconds": "",  # Will be updated at the end
        "matches_found": "",  # Will be updated at the end
        "status": "running",
    }

    run_index_manager.add_run(run_info)

    try:
        # Create analyzer using the public API
        logger.info("=== STARTING PUBLICATION COMPARISON ===")
        logger.info(f"Configuration: {args.max_workers} workers, batch_size={args.batch_size}")
        logger.info(
            f"Thresholds: title={args.title_threshold}, author={args.author_threshold}, "
            f"publisher={args.publisher_threshold}, year_tolerance={args.year_tolerance}"
        )
        # Only log year range if it's actually restricted
        if args.min_year or args.max_year:
            year_from = args.min_year or "earliest"
            year_to = args.max_year or "present"
            logger.info(f"Year range: {year_from} to {year_to}")

        analyzer = MarcCopyrightAnalyzer(
            cache_dir=args.cache_dir if not args.disable_cache else None,
            force_refresh=args.force_refresh,
        )

        # Initialize memory monitor if requested
        memory_monitor = None
        if args.monitor_memory:
            # Local imports
            from marc_pd_tool.shared.utils.memory_utils import MemoryMonitor

            memory_monitor = MemoryMonitor(log_interval=args.memory_log_interval)
            logger.info(f"Memory monitoring enabled (interval: {args.memory_log_interval}s)")

        # Handle ground truth mode
        if args.ground_truth:
            logger.info("=== GROUND TRUTH EXTRACTION MODE ===")

            # Extract ground truth pairs
            ground_truth_pairs, gt_stats = analyzer.extract_ground_truth(
                args.marcxml,
                copyright_dir=args.copyright_dir,
                renewal_dir=args.renewal_dir,
                min_year=args.min_year,
                max_year=args.max_year,
            )

            # Log coverage statistics
            logger.info(f"Found {len(ground_truth_pairs)} ground truth pairs")
            logger.info(
                f"MARC records with LCCN: {gt_stats.marc_with_lccn:,} ({gt_stats.marc_lccn_coverage:.1f}%)"
            )
            logger.info(f"Registration matches: {gt_stats.registration_matches:,}")
            logger.info(f"Renewal matches: {gt_stats.renewal_matches:,}")

            # Export results in all requested formats (skip analysis if no pairs found)
            if ground_truth_pairs:
                # Store pairs in results for export
                analyzer.results.ground_truth_pairs = ground_truth_pairs
                analyzer.results.ground_truth_stats = gt_stats

                # Export ground truth results
                # Note: This will need to be adjusted based on actual API
                logger.info(f"Exporting ground truth results to {output_filename}")

            else:
                logger.warning("No ground truth pairs found - skipping export")

            # Update run info for ground truth mode
            run_info["marc_count"] = str(gt_stats.total_marc_records)
            run_info["duration_seconds"] = str(int(time() - start_time))
            run_info["matches_found"] = str(len(ground_truth_pairs))
            run_info["status"] = "completed"
            run_index_manager.update_run(run_info["log_file"], run_info)

            return  # Exit early for ground truth mode

        # Normal analysis mode or streaming mode
        options: AnalysisOptions = {
            "us_only": args.us_only,
            "min_year": args.min_year,
            "max_year": args.max_year,
            "year_tolerance": args.year_tolerance,
            "title_threshold": args.title_threshold,
            "author_threshold": args.author_threshold,
            "publisher_threshold": args.publisher_threshold,
            "early_exit_title": args.early_exit_title,
            "early_exit_author": args.early_exit_author,
            "early_exit_publisher": args.early_exit_publisher,
            "score_everything": args.score_everything,
            "minimum_combined_score": args.minimum_combined_score,
            "brute_force_missing_year": args.brute_force_missing_year,
            "formats": args.output_formats,
            "single_file": args.single_file,
            "batch_size": args.batch_size,
            "num_processes": args.max_workers,
        }

        # Log memory before processing
        if memory_monitor:
            memory_monitor.force_log("before processing")

        # Choose between streaming and normal mode
        if args.streaming:
            logger.info("Using streaming mode for large dataset processing")
            results = analyzer.analyze_marc_file_streaming(
                args.marcxml,
                copyright_dir=args.copyright_dir,
                renewal_dir=args.renewal_dir,
                output_path=output_filename,
                options=options,
                temp_dir=args.temp_dir,
            )
        else:
            results = analyzer.analyze_marc_file(
                args.marcxml,
                copyright_dir=args.copyright_dir,
                renewal_dir=args.renewal_dir,
                output_path=output_filename,
                options=options,
            )

        # Log memory after processing
        if memory_monitor:
            memory_monitor.force_log("after processing")

        # Get statistics as dict (handle both object and dict cases)
        stats = results.statistics
        if hasattr(stats, "to_dict"):
            stats = stats.to_dict()

        # Compute aggregated statistics for backward compatibility
        pd_records = (
            stats.get("pd_pre_min_year", 0)
            + stats.get("pd_us_not_renewed", 0)
            + stats.get("pd_us_no_reg_data", 0)
            + stats.get("pd_us_reg_no_renewal", 0)
            + stats.get("research_us_only_pd", 0)
        )

        not_pd_records = stats.get("in_copyright", 0) + stats.get("in_copyright_us_renewed", 0)

        undetermined_records = (
            stats.get("unknown_us_no_data", 0)
            + stats.get("research_us_status", 0)
            + stats.get("country_unknown", 0)
        )

        # Log summary (using new function signature)
        end_time = time()
        log_run_summary(
            args=args,
            log_file=log_file_path,
            start_time=start_time,
            end_time=end_time,
            total_records=stats.get("total_records", 0),
            matched_records=stats.get("registration_matches", 0) + stats.get("renewal_matches", 0),
            no_match_records=stats.get("no_matches", 0),
            pd_records=pd_records,
            not_pd_records=not_pd_records,
            undetermined_records=undetermined_records,
            error_records=stats.get("errors", 0),
            skipped_no_year=stats.get("skipped_no_year", 0),
        )

        # Log final memory summary
        if memory_monitor:
            logger.info(memory_monitor.get_final_summary())

        # Update run index with final statistics
        run_info["marc_count"] = str(stats["total_records"])
        run_info["duration_seconds"] = str(int(time() - start_time))
        run_info["matches_found"] = str(stats["registration_matches"] + stats["renewal_matches"])
        run_info["status"] = "completed"
        run_index_manager.update_run(run_info["log_file"], run_info)

    except Exception as e:
        logger.error(f"Error during processing: {e}")
        run_info["status"] = "failed"
        run_info["duration_seconds"] = str(int(time() - start_time))
        run_index_manager.update_run(run_info["log_file"], run_info)
        raise


if __name__ == "__main__":
    main()
