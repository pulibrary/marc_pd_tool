# marc_pd_tool/adapters/cli/parser.py

"""Command-line argument parser configuration"""

# Standard library imports
from argparse import ArgumentParser
from argparse import Namespace
from os import getcwd

# Local imports
from marc_pd_tool.infrastructure.config import get_config


def create_argument_parser() -> ArgumentParser:
    """Create and configure argument parser with all CLI options"""
    # Get current working directory for default paths
    cwd = getcwd()

    # Load default configuration
    config = get_config()

    # Get all config sections with defaults
    processing_config = config.processing
    filtering_config = config.filtering
    output_config = config.output
    caching_config = config.caching
    logging_config = config.logging

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
        choices=["csv", "xlsx", "json", "html"],
        default=["json", "csv"],
        help="Output formats to generate (space-separated). JSON is always generated first. Default: json csv",
    )
    # Single file is False by default, so use store_true to enable it
    parser.add_argument(
        "--single-file",
        action="store_true",
        default=output_config.single_file,
        help=f"Save all results to a single file (default: {output_config.single_file})",
    )

    # Performance options
    parser.add_argument(
        "--batch-size",
        type=int,
        default=processing_config.batch_size,
        help="MARC records per batch",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=processing_config.max_workers,
        help="Number of processes (default: CPU count - 2)",
    )

    # Memory monitoring options
    parser.add_argument(
        "--monitor-memory",
        action="store_true",
        help="Log memory usage statistics during processing",
    )
    parser.add_argument(
        "--memory-log-interval",
        type=int,
        default=60,
        help="Seconds between memory usage logs (default: 60)",
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
        help="Maximum year difference allowed",
    )
    parser.add_argument(
        "--early-exit-title",
        type=int,
        default=config.get_threshold("early_exit_title"),
        help="Title score to skip other comparisons",
    )
    parser.add_argument(
        "--early-exit-author",
        type=int,
        default=config.get_threshold("early_exit_author"),
        help="Author score for high confidence match",
    )
    parser.add_argument(
        "--early-exit-publisher",
        type=int,
        default=config.get_threshold("early_exit_publisher"),
        help="Publisher score for early exit",
    )

    # Filtering options
    parser.add_argument(
        "--min-year",
        type=int,
        default=filtering_config.min_year,
        help="Minimum MARC publication year to process",
    )
    parser.add_argument(
        "--max-year",
        type=int,
        default=filtering_config.max_year,
        help="Maximum MARC publication year to process",
    )
    # US only is False by default, so use store_true to enable it
    parser.add_argument(
        "--us-only",
        action="store_true",
        default=filtering_config.us_only,
        help=f"Only process US publications (default: {filtering_config.us_only})",
    )
    # Brute force is False by default, so use store_true to enable it
    parser.add_argument(
        "--brute-force-missing-year",
        action="store_true",
        default=filtering_config.brute_force_missing_year,
        help=f"Process MARC records without publication year (slow, default: {filtering_config.brute_force_missing_year})",
    )

    # Special analysis modes
    parser.add_argument(
        "--ground-truth",
        action="store_true",
        help="Extract and analyze LCCN-verified ground truth matches",
    )
    # Score everything is False by default, so use store_true to enable it
    parser.add_argument(
        "--score-everything",
        action="store_true",
        default=processing_config.score_everything_mode,
        help="Find best match even below thresholds (for threshold testing)",
    )
    parser.add_argument(
        "--minimum-combined-score",
        type=int,
        default=None,
        help="Minimum combined score for score-everything mode",
    )

    # Cache options
    parser.add_argument(
        "--cache-dir", default=caching_config.cache_dir, help="Directory for cached indexes"
    )
    # Force refresh is False by default, so use store_true to enable it
    parser.add_argument(
        "--force-refresh",
        action="store_true",
        default=caching_config.force_refresh,
        help=f"Force rebuild of cached indexes (default: {caching_config.force_refresh})",
    )
    # Caching is enabled by default (no_cache=False), so use store_true to disable it
    parser.add_argument(
        "--disable-cache",
        action="store_true",
        default=caching_config.no_cache,
        help="Disable caching entirely",
    )

    # Logging options
    parser.add_argument(
        "--log-file",
        default=logging_config.log_file,  # Use config default
        help="Path to log file (default: logs/marc_pd_[timestamp].log)",
    )
    # File logging is enabled by default, so use store_true to disable it
    parser.add_argument("--disable-file-logging", action="store_true", help="Disable file logging")
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",  # Default logging level
        help="Logging level",
    )
    # Silent is False by default, so use store_true to enable it
    parser.add_argument("--silent", action="store_true", help="Suppress console output")

    # Streaming mode options
    # Streaming is False by default, so use store_true to enable it
    parser.add_argument(
        "--streaming", action="store_true", help="Use streaming mode for very large datasets"
    )
    parser.add_argument(
        "--temp-dir", default=None, help="Directory for temporary batch files (streaming mode)"
    )

    # Debug/development options
    # Debug is False by default, so use store_true to enable it
    parser.add_argument(
        "--debug",
        action="store_true",
        default=logging_config.debug,
        help="Enable debug output and detailed logging",
    )

    return parser


def generate_output_filename(args: Namespace) -> str:
    """Generate output filename based on parameters

    Creates descriptive filename including:
    - Timestamp prefix
    - Threshold values (if non-default)
    - Year range
    - US-only flag
    - Special modes (ground-truth, score-everything)

    Args:
        args: Parsed command-line arguments

    Returns:
        Generated filename string with path

    Example:
        "reports/20250201_143052_matches_t50_a40_y1950-1977_us"
    """
    # Standard library imports
    from datetime import datetime
    from os.path import basename
    from os.path import dirname
    from os.path import join

    # Generate timestamp prefix
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Handle user-specified filename
    if hasattr(args, "output_filename") and args.output_filename != "matches.csv":
        # User specified a filename
        base_name = str(args.output_filename)

        # Split into directory and filename
        dir_part = dirname(base_name)
        file_part = basename(base_name)

        # Remove any extension from filename
        if "." in file_part:
            parts = file_part.rsplit(".", 1)
            # Only remove if the extension part is reasonable (< 5 chars)
            if len(parts) > 1 and len(parts[1]) < 5:
                file_part = parts[0]

        # Add timestamp to filename part
        file_part = f"{timestamp}_{file_part}"

        # If user didn't specify a directory, add reports/
        if dir_part == "":
            return join("reports", file_part)
        else:
            return join(dir_part, file_part)

    # Start with base name
    base_name = "matches"

    # Load default configuration for comparison
    config = get_config()

    # Add threshold indicators if non-default
    parts = [base_name]

    if args.title_threshold != config.get_threshold("title"):
        parts.append(f"t{args.title_threshold}")

    if args.author_threshold != config.get_threshold("author"):
        parts.append(f"a{args.author_threshold}")

    if args.publisher_threshold != config.get_threshold("publisher"):
        parts.append(f"p{args.publisher_threshold}")

    # Add year range if specified
    if args.min_year or args.max_year:
        year_part = "y"
        if args.min_year:
            year_part += str(args.min_year)
        else:
            year_part += "0"
        year_part += "-"
        if args.max_year:
            year_part += str(args.max_year)
        else:
            year_part += "9999"
        parts.append(year_part)

    # Add flags
    if args.us_only:
        parts.append("us")

    if args.score_everything:
        parts.append("all")

    if args.ground_truth:
        parts.append("gt")

    # Join with underscores
    filename = "_".join(parts)

    # Add timestamp prefix and reports directory
    filename_with_timestamp = f"{timestamp}_{filename}"
    return join("reports", filename_with_timestamp)
