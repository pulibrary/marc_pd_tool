"""Core processing logic for matching, indexing, and analysis"""

# Local imports
from marc_pd_tool.processing.default_matching import DefaultMatchingEngine
from marc_pd_tool.processing.default_matching import DynamicWeightingCombiner
from marc_pd_tool.processing.default_matching import FuzzyWuzzySimilarityCalculator
from marc_pd_tool.processing.generic_title_detector import GenericTitleDetector
from marc_pd_tool.processing.indexer import PublicationIndex
from marc_pd_tool.processing.indexer import build_index
from marc_pd_tool.processing.matching_api import MatchingEngine
from marc_pd_tool.processing.matching_api import ScoreCombiner
from marc_pd_tool.processing.matching_api import SimilarityCalculator
from marc_pd_tool.processing.matching_api import SimilarityScores
from marc_pd_tool.processing.matching_engine import find_best_match
from marc_pd_tool.processing.matching_engine import process_batch

__all__ = [
    "DefaultMatchingEngine",
    "DynamicWeightingCombiner",
    "FuzzyWuzzySimilarityCalculator",
    "GenericTitleDetector",
    "PublicationIndex",
    "build_index",
    "MatchingEngine",
    "ScoreCombiner",
    "SimilarityCalculator",
    "SimilarityScores",
    "find_best_match",
    "process_batch",
]
