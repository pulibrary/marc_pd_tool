# marc_pd_tool/adapters/cli/__init__.py

"""CLI adapter for MARC PD Tool"""

# Local imports
from marc_pd_tool.adapters.cli.logging_setup import get_default_log_path
from marc_pd_tool.adapters.cli.logging_setup import log_run_summary
from marc_pd_tool.adapters.cli.logging_setup import set_up_logging
from marc_pd_tool.adapters.cli.main import main
from marc_pd_tool.adapters.cli.parser import create_argument_parser
from marc_pd_tool.adapters.cli.parser import generate_output_filename

__all__ = [
    "create_argument_parser",
    "generate_output_filename",
    "get_default_log_path",
    "set_up_logging",
    "log_run_summary",
    "main",
]
