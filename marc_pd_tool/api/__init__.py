# marc_pd_tool/api/__init__.py

"""API module for MARC copyright analysis

This module provides the high-level API for analyzing MARC records
against copyright and renewal data.
"""

# Local imports
# Import from the new modular structure
from marc_pd_tool.api._analyzer import MarcCopyrightAnalyzer
from marc_pd_tool.api._results import AnalysisResults

__all__ = ["AnalysisResults", "MarcCopyrightAnalyzer"]
