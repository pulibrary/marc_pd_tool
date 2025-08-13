# marc_pd_tool/application/processing/matching/__init__.py

"""Matching module for copyright data comparison"""

# Local imports
from marc_pd_tool.application.processing.matching._core_matcher import CoreMatcher
from marc_pd_tool.application.processing.matching._lccn_matcher import LCCNMatcher
from marc_pd_tool.application.processing.matching._match_builder import (
    MatchResultBuilder,
)
from marc_pd_tool.application.processing.matching._score_combiner import ScoreCombiner

__all__ = ["CoreMatcher", "LCCNMatcher", "MatchResultBuilder", "ScoreCombiner"]
