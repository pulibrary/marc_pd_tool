# marc_pd_tool/cli.py

"""
Backward compatibility wrapper for CLI

This module provides backward compatibility for scripts/tests that import from marc_pd_tool.cli.
All actual implementation is in marc_pd_tool.adapters.cli.
"""

# Standard library imports
from argparse import Namespace
from logging import getLogger
from time import time

# Create module logger for tests
logger = getLogger(__name__)

# Local imports
# Re-export the main analyzer for tests that expect it here
from marc_pd_tool import MarcCopyrightAnalyzer
from marc_pd_tool.adapters.cli.logging_setup import (
    log_run_summary as _log_run_summary_new,
)
from marc_pd_tool.adapters.cli.logging_setup import get_default_log_path
from marc_pd_tool.adapters.cli.logging_setup import set_up_logging

# Re-export everything from the proper location
from marc_pd_tool.adapters.cli.main import main
from marc_pd_tool.adapters.cli.parser import create_argument_parser
from marc_pd_tool.adapters.cli.parser import generate_output_filename

# Re-export RunIndexManager for tests
from marc_pd_tool.infrastructure import RunIndexManager


# Backward compatibility wrapper for old tests
def log_run_summary(
    start_time: float, results_stats: dict[str, int], output_file: str, args: Namespace
) -> None:
    """Legacy wrapper for log_run_summary - for backward compatibility with tests

    The old signature took:
        - start_time: float
        - results_stats: dict with all statistics
        - output_file: str (not used by new function)
        - args: Namespace

    The new signature requires:
        - args: Namespace
        - log_file: str | None
        - start_time: float
        - end_time: float
        - total_records: int
        - matched_records: int
        - no_match_records: int
        - pd_records: int
        - not_pd_records: int
        - undetermined_records: int
        - error_records: int
        - skipped_no_year: int = 0
    """
    end_time = time()

    # Extract statistics from old format
    total_records = results_stats.get("total_records", 0)
    matched_records = results_stats.get("registration_matches", 0) + results_stats.get(
        "renewal_matches", 0
    )
    no_match_records = results_stats.get("no_match", results_stats.get("no_matches", 0))

    # Compute aggregated pd records
    pd_records = results_stats.get(
        "pd",
        results_stats.get("pd_pre_min_year", 0)
        + results_stats.get("pd_us_not_renewed", 0)
        + results_stats.get("pd_us_no_reg_data", 0)
        + results_stats.get("pd_us_reg_no_renewal", 0)
        + results_stats.get("research_us_only_pd", 0)
        + results_stats.get("us_registered_not_renewed", 0)
        + results_stats.get("us_pre_1929", 0),
    )

    # Compute aggregated not_pd records
    not_pd_records = results_stats.get(
        "not_pd",
        results_stats.get("in_copyright", 0)
        + results_stats.get("in_copyright_us_renewed", 0)
        + results_stats.get("us_renewed", 0),
    )

    # Compute aggregated undetermined records
    undetermined_records = results_stats.get(
        "undetermined",
        results_stats.get("unknown_us_no_data", 0)
        + results_stats.get("research_us_status", 0)
        + results_stats.get("country_unknown", 0)
        + results_stats.get("country_unknown_no_match", 0)
        + results_stats.get("foreign_no_match_gbr", 0)
        + results_stats.get("foreign_renewed_fra", 0),
    )

    error_records = results_stats.get("errors", 0)
    skipped_no_year = results_stats.get("skipped_no_year", 0)

    # Call new function with expanded parameters
    _log_run_summary_new(
        args=args,
        log_file=None,
        start_time=start_time,
        end_time=end_time,
        total_records=total_records,
        matched_records=matched_records,
        no_match_records=no_match_records,
        pd_records=pd_records,
        not_pd_records=not_pd_records,
        undetermined_records=undetermined_records,
        error_records=error_records,
        skipped_no_year=skipped_no_year,
    )


__all__ = [
    "MarcCopyrightAnalyzer",
    "RunIndexManager",
    "create_argument_parser",
    "generate_output_filename",
    "get_default_log_path",
    "log_run_summary",
    "main",
    "set_up_logging",
]
