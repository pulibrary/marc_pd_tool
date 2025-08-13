# marc_pd_tool/__init__.py

"""MARC Publication Data Tool Package

A library for analyzing MARC bibliographic records against US copyright
registration and renewal data to determine copyright status.
"""

# Standard library imports

# Local imports
# High-level API
from marc_pd_tool.adapters.api import AnalysisResults
from marc_pd_tool.adapters.api import MarcCopyrightAnalyzer
from marc_pd_tool.application.models.ground_truth_stats import GroundTruthStats
from marc_pd_tool.application.processing.ground_truth_extractor import (
    GroundTruthExtractor,
)
from marc_pd_tool.application.processing.matching_engine import DataMatcher

# Data models (for advanced users)
from marc_pd_tool.core.domain.enums import CopyrightStatus
from marc_pd_tool.core.domain.enums import CountryClassification
from marc_pd_tool.core.domain.enums import MatchType
from marc_pd_tool.core.domain.match_result import MatchResult
from marc_pd_tool.core.domain.publication import Publication

# For users who want lower-level control
from marc_pd_tool.infrastructure import CacheManager
from marc_pd_tool.infrastructure.config import ConfigLoader
from marc_pd_tool.infrastructure.persistence import CopyrightDataLoader
from marc_pd_tool.infrastructure.persistence import MarcLoader
from marc_pd_tool.infrastructure.persistence import RenewalDataLoader

# Version info
__version__ = "0.1.0"

__all__: list[str] = [
    # Primary API
    "MarcCopyrightAnalyzer",
    "AnalysisResults",
    # Data models
    "Publication",
    "MatchResult",
    "CopyrightStatus",
    "CountryClassification",
    "MatchType",
    # Ground truth
    "GroundTruthStats",
    # Advanced usage - loaders
    "MarcLoader",
    "CopyrightDataLoader",
    "RenewalDataLoader",
    # Advanced usage - processing
    "DataMatcher",
    "GroundTruthExtractor",
    # Advanced usage - infrastructure
    "ConfigLoader",
    "CacheManager",
    # Version
    "__version__",
]
