# marc_pd_tool/infrastructure/logging/_setup.py

"""Logging configuration and setup for CLI"""

# Standard library imports
from argparse import Namespace
from datetime import datetime
from logging import DEBUG
from logging import FileHandler
from logging import Formatter
from logging import INFO
from logging import StreamHandler
from logging import getLogger
from os import makedirs
from os.path import exists

# Local imports
from marc_pd_tool.infrastructure import RunIndexManager


def get_default_log_path() -> str:
    """Generate default log file path with timestamp"""
    # Create logs directory if it doesn't exist
    log_dir = "logs"
    if not exists(log_dir):
        makedirs(log_dir)

    # Generate filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = f"marc_pd_{timestamp}.log"

    # Get run index for this session
    run_index_manager = RunIndexManager()
    run_index = run_index_manager.get_next_run_index()

    # Include run index in filename
    log_filename = f"marc_pd_{timestamp}_run{run_index:03d}.log"

    return f"{log_dir}/{log_filename}"


def set_up_logging(
    log_file: str | None = None,
    log_level: str = "INFO",
    silent: bool = False,
    disable_file_logging: bool = False,
) -> str | None:
    """Configure logging for the application

    Args:
        log_file: Path to log file (auto-generated if None and file logging enabled)
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        silent: If True, suppress console output
        disable_file_logging: If True, disable file logging

    Returns:
        Path to log file if file logging is enabled, None otherwise
    """
    # Convert log level string to logging constant
    level = getattr(getLogger(), log_level, INFO)

    # Configure root logger
    root_logger = getLogger()
    root_logger.setLevel(level)

    # Clear any existing handlers
    root_logger.handlers = []

    # Create formatters - use consistent format for both console and file
    # Console gets abbreviated timestamp, file gets full details
    console_formatter = Formatter("%(asctime)s - %(levelname)s - %(message)s")
    file_formatter = Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    # Add console handler unless silent
    if not silent:
        console_handler = StreamHandler()
        console_handler.setLevel(level)
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)

    # Add file handler unless disabled
    if not disable_file_logging:
        if log_file is None:
            log_file = get_default_log_path()

        file_handler = FileHandler(log_file)
        file_handler.setLevel(DEBUG)  # Always log debug to file
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

        # Log startup information
        logger = getLogger(__name__)
        logger.info(f"Logging to file: {log_file}")

        return log_file

    return None


def log_run_summary(
    args: Namespace,
    log_file: str | None,
    start_time: float,
    end_time: float,
    total_records: int,
    matched_records: int,
    no_match_records: int,
    pd_records: int,
    not_pd_records: int,
    undetermined_records: int,
    error_records: int,
    skipped_no_year: int = 0,
) -> None:
    """Log final run summary with statistics

    Args:
        args: Parsed command-line arguments
        log_file: Path to log file (if any)
        start_time: Processing start time
        end_time: Processing end time
        total_records: Total records processed
        matched_records: Records with matches
        no_match_records: Records without matches
        pd_records: Public domain records
        not_pd_records: Not public domain records
        undetermined_records: Undetermined status records
        error_records: Records with errors
        skipped_no_year: Records skipped due to missing year (default 0)
    """
    logger = getLogger(__name__)

    # Calculate processing time
    processing_time = end_time - start_time
    minutes = int(processing_time // 60)
    seconds = int(processing_time % 60)

    # Calculate rates
    records_per_second = total_records / processing_time if processing_time > 0 else 0
    records_per_minute = records_per_second * 60

    # Calculate total input records
    total_input = total_records + skipped_no_year

    # Build summary message
    summary_lines = ["\n" + "=" * 80, "PROCESSING COMPLETE", "=" * 80]

    # Show total input records if different from processed
    if skipped_no_year > 0:
        summary_lines.extend(
            [
                f"Total input records: {total_input:,}",
                f"Records analyzed: {total_records:,}",
                f"Records skipped (no year): {skipped_no_year:,}",
            ]
        )
    else:
        summary_lines.append(f"Total records processed: {total_records:,}")

    summary_lines.extend(
        [
            f"Processing time: {minutes}m {seconds}s",
            f"Processing rate: {records_per_minute:.0f} records/minute",
        ]
    )

    # Only show statistics if records were actually processed
    if total_records > 0:
        # Calculate percentages
        matched_pct = matched_records / total_records * 100
        no_match_pct = no_match_records / total_records * 100
        pd_pct = pd_records / total_records * 100
        not_pd_pct = not_pd_records / total_records * 100
        undetermined_pct = undetermined_records / total_records * 100

        summary_lines.extend(
            [
                "",
                "Match Statistics:",
                f"  Matched: {matched_records:,} ({matched_pct:.1f}%)",
                f"  No match: {no_match_records:,} ({no_match_pct:.1f}%)",
                "",
                "Copyright Status:",
                f"  Public Domain: {pd_records:,} ({pd_pct:.1f}%)",
                f"  Not Public Domain: {not_pd_records:,} ({not_pd_pct:.1f}%)",
                f"  Undetermined: {undetermined_records:,} ({undetermined_pct:.1f}%)",
            ]
        )
    elif skipped_no_year > 0:
        # All records were skipped
        summary_lines.extend(
            [
                "",
                "No records were analyzed (all skipped due to missing year data).",
                "Use --brute-force-missing-year to process records without publication years.",
            ]
        )

    if error_records > 0:
        summary_lines.append(f"  Errors: {error_records:,}")

    # Add configuration summary
    # Get config for threshold values
    # Local imports
    from marc_pd_tool.infrastructure.config import get_config

    config = get_config()

    summary_lines.extend(
        [
            "",
            "Configuration:",
            f"  Title threshold: {config.get_threshold('title')}%",
            f"  Author threshold: {config.get_threshold('author')}%",
            f"  Year tolerance: ±{config.get_threshold('year_tolerance')}",
        ]
    )

    if args.min_year or args.max_year:
        year_range = f"{args.min_year or 'earliest'} - {args.max_year or 'latest'}"
        summary_lines.append(f"  Year range: {year_range}")

    if args.us_only:
        summary_lines.append("  US publications only: Yes")

    # Add output information
    summary_lines.extend(["", "Output:"])

    if hasattr(args, "output_file"):
        summary_lines.append(f"  Results: {args.output_file}")

    if log_file:
        summary_lines.append(f"  Log: {log_file}")

    summary_lines.append("=" * 80)

    # Log the summary
    summary = "\n".join(summary_lines)
    logger.info(summary)
