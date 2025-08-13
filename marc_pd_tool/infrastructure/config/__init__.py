# marc_pd_tool/infrastructure/config/__init__.py

"""Configuration infrastructure for the MARC PD Tool.

This module manages configuration loading, validation, and models.
"""

# Local imports
from marc_pd_tool.infrastructure.config._loader import ConfigLoader
from marc_pd_tool.infrastructure.config._loader import get_config
from marc_pd_tool.infrastructure.config._shared_models import GenericDetectorConfig
from marc_pd_tool.infrastructure.config._shared_models import MatchingConfig
from marc_pd_tool.infrastructure.config._shared_models import ScoringWeights
from marc_pd_tool.infrastructure.config._wordlists import WordlistsConfig as Wordlists

__all__ = [
    "ConfigLoader",
    "get_config",
    "GenericDetectorConfig",
    "MatchingConfig",
    "ScoringWeights",
    "Wordlists",
]
