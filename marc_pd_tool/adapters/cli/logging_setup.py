# marc_pd_tool/adapters/cli/logging_setup.py

"""Compatibility wrapper for logging setup.

This module re-exports from the new infrastructure location.
"""

# Local imports
from marc_pd_tool.infrastructure.logging import get_default_log_path
from marc_pd_tool.infrastructure.logging import log_run_summary
from marc_pd_tool.infrastructure.logging import setup_logging as set_up_logging

# For compatibility, export both names
setup_logging = set_up_logging

__all__ = ["set_up_logging", "setup_logging", "get_default_log_path", "log_run_summary"]
