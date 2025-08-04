"""
MARC Publication Data Comparison Tool - CLI Module

Command-line interface for comparing MARC publication data
with copyright registry entries to identify potential matches.

This CLI uses the public API provided by marc_pd_tool.
"""

# Standard library imports
from argparse import ArgumentParser
from argparse import BooleanOptionalAction
from argparse import Namespace
from datetime import datetime
from logging import DEBUG
from logging import FileHandler
from logging import Formatter
from logging import INFO
from logging import StreamHandler
from logging import getLogger
from multiprocessing import cpu_count
from os import getcwd
from os import makedirs
from os.path import dirname
from os.path import exists
from os.path import join
from time import time

# Local imports
from marc_pd_tool import MarcCopyrightAnalyzer
from marc_pd_tool.infrastructure.config_loader import get_config
from marc_pd_tool.infrastructure.run_index_manager import RunIndexManager
from marc_pd_tool.utils.types import AnalysisOptions

logger = getLogger(__name__)


def get_default_log_path() -> str:
    """Generate default log file path with timestamp"""
    # Create logs directory if it doesn't exist
    log_dir = "logs"
    if not exists(log_dir):
        makedirs(log_dir)

    # Generate filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = f"marc_pd_{timestamp}.log"

    return join(log_dir, log_filename)


def set_up_logging(
    log_file: str | None = None, debug: bool = False, use_default_log: bool = True
) -> str:
    """Configure logging to console and optionally to file

    Returns:
        str: Path to the log file being used (or empty string if no file logging)
    """
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

    # Determine log file path
    actual_log_file = None
    if log_file:
        # User specified a log file
        actual_log_file = log_file
    elif use_default_log:
        # Use default log file
        actual_log_file = get_default_log_path()

    # Add file handler if we have a log file
    if actual_log_file:
        file_handler = FileHandler(actual_log_file)
        file_handler.setLevel(log_level)
        file_handler.setFormatter(Formatter(formatter_str))
        root_logger.addHandler(file_handler)

    # Set root logger level
    root_logger.setLevel(log_level)

    return actual_log_file or ""


def create_argument_parser() -> ArgumentParser:
    """Create and configure argument parser with all CLI options"""
    # Get current working directory for default paths
    cwd = getcwd()

    # Load default configuration
    config = get_config()

    # Get all config sections with defaults
    processing_config = config.get_processing_config()
    filtering_config = config.get_filtering_config()
    output_config = config.get_output_config()
    caching_config = config.get_caching_config()
    logging_config = config.get_logging_config()

    parser = ArgumentParser(
        description="Compare MARC publication data with copyright registry entries",
        epilog="For detailed documentation, see: https://github.com/jstroop/marc_pd_tool",
    )

    # Required arguments
    parser.add_argument(
        "--marcxml", required=True, help="Path to MARC XML file or directory of MARC files"
    )

    # Data source directories
    parser.add_argument(
        "--copyright-dir",
        default=f"{cwd}/nypl-reg/xml",
        help="Path to copyright registration XML directory",
    )
    parser.add_argument(
        "--renewal-dir", default=f"{cwd}/nypl-ren/data", help="Path to renewal TSV directory"
    )

    # Output options
    parser.add_argument(
        "--output-filename",
        "-o",
        default="matches.csv",
        help="Output file (default: reports/[auto-generated name based on filters])",
    )
    parser.add_argument(
        "--output-formats",
        nargs="+",
        choices=["csv", "xlsx", "xlsx-stacked", "json", "html"],
        default=["json", "csv"],
        help="Output formats to generate (space-separated). JSON is always generated first. Default: json csv",
    )
    parser.add_argument(
        "--single-file",
        action=BooleanOptionalAction,
        default=output_config.get("single_file", False),
        help=f"Save all results to a single file (default: {output_config.get('single_file', False)})",
    )

    # Performance options
    parser.add_argument(
        "--batch-size",
        type=int,
        default=processing_config.get("batch_size", 100),
        help="MARC records per batch",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=processing_config.get("max_workers"),
        help="Number of processes (default: CPU count - 2)",
    )

    # Matching thresholds
    parser.add_argument(
        "--title-threshold",
        type=int,
        default=config.get_threshold("title"),
        help="Minimum title similarity score (0-100)",
    )
    parser.add_argument(
        "--author-threshold",
        type=int,
        default=config.get_threshold("author"),
        help="Minimum author similarity score (0-100)",
    )
    parser.add_argument(
        "--publisher-threshold",
        type=int,
        default=config.get_threshold("publisher"),
        help="Minimum publisher similarity score (0-100)",
    )
    parser.add_argument(
        "--year-tolerance",
        type=int,
        default=config.get_threshold("year_tolerance"),
        help="Maximum year difference for matching",
    )
    parser.add_argument(
        "--early-exit-title",
        type=int,
        default=config.get_threshold("early_exit_title"),
        help="Title score for early termination (default: from config)",
    )
    parser.add_argument(
        "--early-exit-author",
        type=int,
        default=config.get_threshold("early_exit_author"),
        help="Author score for early termination (default: from config)",
    )
    parser.add_argument(
        "--early-exit-publisher",
        type=int,
        default=config.get_threshold("early_exit_publisher"),
        help="Publisher score for early termination (default: from config)",
    )

    # Filtering options
    # Calculate default min_year as current year - 96 if not in config
    default_min_year = filtering_config.get("min_year")
    if default_min_year is None:
        current_year = datetime.now().year
        default_min_year = current_year - 96

    parser.add_argument(
        "--min-year",
        type=int,
        default=default_min_year,
        help=f"Minimum publication year to include (default: {default_min_year})",
    )
    parser.add_argument(
        "--max-year",
        type=int,
        default=filtering_config.get("max_year"),
        help="Maximum publication year to include (default: no limit)",
    )
    parser.add_argument(
        "--us-only",
        action=BooleanOptionalAction,
        default=filtering_config.get("us_only", False),
        help=f"Only process US publications (default: {filtering_config.get('us_only', False)})",
    )

    # Threshold tuning modes
    parser.add_argument(
        "--score-everything-mode",
        action=BooleanOptionalAction,
        default=processing_config.get("score_everything_mode", False),
        help=f"Find best match for every record regardless of thresholds (default: {processing_config.get('score_everything_mode', False)})",
    )
    parser.add_argument(
        "--minimum-combined-score",
        type=int,
        default=config.get_threshold("minimum_combined_score"),
        help="Minimum combined score for matches in score-everything mode",
    )
    parser.add_argument(
        "--brute-force-missing-year",
        action=BooleanOptionalAction,
        default=processing_config.get("brute_force_missing_year", False),
        help=f"Process records without year data (default: {processing_config.get('brute_force_missing_year', False)})",
    )

    # Generic title detection
    parser.add_argument(
        "--generic-title-threshold",
        type=int,
        default=config.get_generic_detector_config()["frequency_threshold"],
        help="Minimum occurrences for a title to be considered generic",
    )
    parser.add_argument(
        "--disable-generic-detection",
        action="store_true",
        help="Disable generic title detection and use normal scoring for all titles",
    )

    parser.add_argument(
        "--ground-truth-mode",
        action="store_true",
        help="Extract LCCN-verified matches and analyze their similarity scores (for threshold analysis)",
    )

    # Configuration options
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to JSON configuration file for scoring weights and thresholds",
    )

    # Cache options
    parser.add_argument(
        "--cache-dir",
        type=str,
        default=caching_config.get("cache_dir", ".marcpd_cache"),
        help="Directory for persistent data cache",
    )
    parser.add_argument(
        "--force-refresh",
        action=BooleanOptionalAction,
        default=caching_config.get("force_refresh", False),
        help=f"Force refresh of all cached data (default: {caching_config.get('force_refresh', False)})",
    )
    parser.add_argument(
        "--disable-cache",
        action=BooleanOptionalAction,
        default=caching_config.get("no_cache", False),
        help=f"Disable caching entirely (default: {caching_config.get('no_cache', False)})",
    )

    # Logging options
    parser.add_argument(
        "--log-file",
        type=str,
        default=logging_config.get("log_file"),
        help="Write logs to specified file",
    )
    parser.add_argument(
        "--debug",
        action=BooleanOptionalAction,
        default=logging_config.get("debug", False),
        help=f"Enable DEBUG level logging (default: {logging_config.get('debug', False)})",
    )
    parser.add_argument(
        "--no-log-file", action="store_true", help="Disable file logging (console output only)"
    )

    return parser


def generate_output_filename(args: Namespace) -> str:
    """Generate descriptive output filename based on filters"""
    if args.output_filename != "matches.csv":
        # User specified a filename - check if it already includes a directory
        base_name = str(args.output_filename)

        # If user didn't specify a directory, add reports/
        if dirname(base_name) == "":
            base_name = join("reports", base_name)

        # Remove any existing extension (more broadly)
        if "." in base_name:
            # Split on last dot to handle paths with dots
            parts = base_name.rsplit(".", 1)
            # Only remove if the extension part is reasonable (< 5 chars)
            if len(parts) > 1 and len(parts[1]) < 5:
                base_name = parts[0]
        # Remove any extension from base name
        return base_name

    # Build filename components
    components = [
        (
            "ground_truth"
            if hasattr(args, "ground_truth_mode") and args.ground_truth_mode
            else "matches"
        )
    ]

    if args.us_only:
        components.append("us-only")

    if args.min_year or args.max_year:
        year_part = f"{args.min_year or 'pre'}-{args.max_year or 'current'}"
        components.append(year_part)

    if args.score_everything_mode:
        components.append("score-everything")

    # Return base name without extension (will be added by exporters)
    filename = "_".join(components)

    # Add reports directory
    return join("reports", filename)


def log_run_summary(
    start_time: float, results_stats: dict[str, int], output_file: str, args: Namespace
) -> None:
    """Log summary of the run"""
    duration = time() - start_time

    # Calculate rates
    records_per_second = results_stats["total_records"] / duration if duration > 0 else 0
    records_per_minute = records_per_second * 60

    logger.info("=" * 80)
    logger.info("PROCESSING COMPLETE")
    logger.info("=" * 80)
    logger.info(f"Total records processed: {results_stats['total_records']:,}")
    if results_stats.get("skipped_no_year", 0) > 0:
        logger.info(f"Records skipped (no year): {results_stats['skipped_no_year']:,}")
    logger.info(f"Registration matches: {results_stats['registration_matches']:,}")
    logger.info(f"Renewal matches: {results_stats['renewal_matches']:,}")
    logger.info(f"Processing time: {duration:.2f} seconds")
    logger.info(f"Processing rate: {records_per_minute:.0f} records/minute")
    logger.info(f"Output written to: {output_file}")
    logger.info("=" * 80)

    # Log copyright status breakdown
    logger.info("Copyright Status Breakdown:")
    for status in [
        "pd_no_renewal",
        "pd_date_verify",
        "in_copyright",
        "research_us_status",
        "research_us_only_pd",
        "country_unknown",
    ]:
        if status in results_stats:
            logger.info(f"  {status.upper()}: {results_stats[status]:,}")


def main() -> None:
    """Main CLI entry point using the public API"""
    parser = create_argument_parser()
    args = parser.parse_args()

    # Log the min_year being used
    if args.min_year is not None:
        logger.info(f"Using min_year filter: {args.min_year}")

    # Validate year range
    if args.max_year is not None and args.max_year < args.min_year:
        raise ValueError(
            f"Max year ({args.max_year}) cannot be less than min year ({args.min_year})"
        )

    # Force single-file output when score-everything mode is enabled
    if args.score_everything_mode:
        args.single_file = True

    # Set number of workers
    if args.max_workers is None:
        args.max_workers = max(1, cpu_count() - 2)  # Use all cores minus 2, minimum 1

    # Configure logging
    log_file_path = set_up_logging(
        log_file=args.log_file, debug=args.debug, use_default_log=not args.no_log_file
    )

    if log_file_path:
        logger.info(f"Logging to file: {log_file_path}")

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
        "score_everything_mode": str(args.score_everything_mode),
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

        analyzer = MarcCopyrightAnalyzer(
            config_path=args.config,
            cache_dir=args.cache_dir if not args.disable_cache else None,
            force_refresh=args.force_refresh,
        )

        # Handle ground truth mode
        if args.ground_truth_mode:
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

            # Analyze scores
            analyzer.analyze_ground_truth_scores(ground_truth_pairs)

            # Export results
            # For ground truth, use the first format specified
            analyzer.export_ground_truth_analysis(
                output_filename, output_format=args.output_formats[0]
            )

            # Update run info for ground truth mode
            run_info["marc_count"] = str(gt_stats.total_marc_records)
            run_info["duration_seconds"] = str(int(time() - start_time))
            run_info["matches_found"] = str(len(ground_truth_pairs))
            run_info["status"] = "completed"
            run_index_manager.update_run(run_info["log_file"], run_info)

            return  # Exit early for ground truth mode

        # Normal analysis mode
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
            "score_everything_mode": args.score_everything_mode,
            "brute_force_missing_year": args.brute_force_missing_year,
            "formats": args.output_formats,
            "single_file": args.single_file,
            "batch_size": args.batch_size,
            "num_processes": args.max_workers,
        }

        results = analyzer.analyze_marc_file(
            args.marcxml,
            copyright_dir=args.copyright_dir,
            renewal_dir=args.renewal_dir,
            output_path=output_filename,
            options=options,
        )

        # Get statistics
        stats = results.statistics

        # Log summary
        log_run_summary(start_time, stats, output_filename, args)

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
