# marc_pd_tool/infrastructure/logging/__init__.py

"""Logging infrastructure for the MARC PD Tool.

This module provides centralized logging configuration and setup.
"""

# Local imports
from marc_pd_tool.infrastructure.logging._setup import get_default_log_path
from marc_pd_tool.infrastructure.logging._setup import log_run_summary
from marc_pd_tool.infrastructure.logging._setup import set_up_logging as setup_logging

__all__ = ["setup_logging", "get_default_log_path", "log_run_summary"]
