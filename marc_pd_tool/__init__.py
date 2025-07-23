# marc_pd_tool/__init__.py

"""MARC Publication Data Tool Package

A library for analyzing MARC bibliographic records against US copyright
registration and renewal data to determine copyright status.
"""

# Standard library imports

# Local imports
# High-level API
from marc_pd_tool.api import AnalysisResults
from marc_pd_tool.api import MarcCopyrightAnalyzer

# Data models (for advanced users)
from marc_pd_tool.data.enums import CopyrightStatus
from marc_pd_tool.data.enums import CountryClassification
from marc_pd_tool.data.publication import MatchResult
from marc_pd_tool.data.publication import Publication

# For users who want lower-level control
from marc_pd_tool.infrastructure.cache_manager import CacheManager
from marc_pd_tool.infrastructure.config_loader import ConfigLoader
from marc_pd_tool.loaders.copyright_loader import CopyrightDataLoader
from marc_pd_tool.loaders.marc_loader import MarcLoader
from marc_pd_tool.loaders.renewal_loader import RenewalDataLoader
from marc_pd_tool.processing.matching_engine import DataMatcher

# Version info
__version__ = "1.0.0"

__all__: list[str] = [
    # Primary API
    "MarcCopyrightAnalyzer",
    "AnalysisResults",
    # Data models
    "Publication",
    "MatchResult",
    "CopyrightStatus",
    "CountryClassification",
    # Advanced usage - loaders
    "MarcLoader",
    "CopyrightDataLoader",
    "RenewalDataLoader",
    # Advanced usage - processing
    "DataMatcher",
    # Advanced usage - infrastructure
    "ConfigLoader",
    "CacheManager",
    # Version
    "__version__",
]
