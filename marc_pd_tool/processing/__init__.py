# marc_pd_tool/processing/__init__.py

"""Core processing logic for matching, indexing, and analysis"""

# Local imports
from marc_pd_tool.processing.indexer import CompactIndexEntry
from marc_pd_tool.processing.indexer import DataIndexer
from marc_pd_tool.processing.indexer import build_wordbased_index
from marc_pd_tool.processing.matching_engine import DataMatcher
from marc_pd_tool.processing.matching_engine import init_worker
from marc_pd_tool.processing.matching_engine import process_batch
from marc_pd_tool.processing.similarity_calculator import SimilarityCalculator
from marc_pd_tool.processing.text_processing import GenericTitleDetector
from marc_pd_tool.processing.text_processing import LanguageProcessor
from marc_pd_tool.processing.text_processing import MultiLanguageStemmer
from marc_pd_tool.processing.text_processing import expand_abbreviations
from marc_pd_tool.processing.text_processing import extract_best_publisher_match

__all__: list[str] = [
    "DataMatcher",
    "SimilarityCalculator",
    "LanguageProcessor",
    "MultiLanguageStemmer",
    "expand_abbreviations",
    "GenericTitleDetector",
    "CompactIndexEntry",
    "DataIndexer",
    "build_wordbased_index",
    "extract_best_publisher_match",
    "init_worker",
    "process_batch",
]
