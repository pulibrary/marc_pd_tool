"""Core data models and structures for MARC publication analysis"""

# Data models
# Local imports
from marc_pd_tool.data.enums import CopyrightStatus
from marc_pd_tool.data.enums import CountryClassification
from marc_pd_tool.data.publication import MatchResult
from marc_pd_tool.data.publication import Publication

__all__ = ["CopyrightStatus", "CountryClassification", "MatchResult", "Publication"]
