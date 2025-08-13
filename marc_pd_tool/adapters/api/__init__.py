# marc_pd_tool/adapters/api/__init__.py

"""API module for MARC copyright analysis

This module provides the high-level API for analyzing MARC records
against copyright and renewal data.
"""

# Local imports
from marc_pd_tool.adapters.api._analyzer import MarcCopyrightAnalyzer

# Import from the new modular structure
from marc_pd_tool.application.models.analysis_results import AnalysisResults

__all__ = ["AnalysisResults", "MarcCopyrightAnalyzer"]
