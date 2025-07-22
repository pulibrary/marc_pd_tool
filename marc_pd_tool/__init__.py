"""MARC Publication Data Tool Package"""

# Local imports
from marc_pd_tool.data.enums import CopyrightStatus
from marc_pd_tool.data.enums import CountryClassification
from marc_pd_tool.data.publication import MatchResult
from marc_pd_tool.data.publication import Publication
from marc_pd_tool.exporters.csv_exporter import save_matches_csv
from marc_pd_tool.loaders.copyright_loader import CopyrightDataLoader
from marc_pd_tool.loaders.marc_extractor import ParallelMarcExtractor
from marc_pd_tool.loaders.renewal_loader import RenewalDataLoader
from marc_pd_tool.processing.default_matching import DefaultMatchingEngine
from marc_pd_tool.processing.default_matching import DynamicWeightingCombiner
from marc_pd_tool.processing.default_matching import FuzzyWuzzySimilarityCalculator
from marc_pd_tool.processing.indexer import PublicationIndex
from marc_pd_tool.processing.indexer import build_index
from marc_pd_tool.processing.matching_api import MatchingEngine
from marc_pd_tool.processing.matching_api import ScoreCombiner
from marc_pd_tool.processing.matching_api import SimilarityCalculator
from marc_pd_tool.processing.matching_api import SimilarityScores
from marc_pd_tool.processing.matching_engine import find_best_match
from marc_pd_tool.processing.matching_engine import process_batch
from marc_pd_tool.utils.marc_utilities import extract_country_from_marc_008

__all__ = [
    # Core data structures
    "Publication",
    "MatchResult",
    "CopyrightStatus",
    "CountryClassification",
    # Data loaders
    "CopyrightDataLoader",
    "RenewalDataLoader",
    "ParallelMarcExtractor",
    # Processing functions
    "process_batch",
    "find_best_match",
    # Indexing
    "PublicationIndex",
    "build_index",
    # Utilities
    "save_matches_csv",
    "extract_country_from_marc_008",
    # Matching and Scoring API
    "SimilarityCalculator",
    "ScoreCombiner",
    "MatchingEngine",
    "SimilarityScores",
    # Default Implementations
    "FuzzyWuzzySimilarityCalculator",
    "DynamicWeightingCombiner",
    "DefaultMatchingEngine",
]
