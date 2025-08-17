# marc_pd_tool/core/types/__init__.py

"""Type definitions for the MARC PD Tool

This package contains all type definitions, protocols, and type aliases
used throughout the codebase. These are pure type definitions with no
implementation logic.
"""

# Local imports
from marc_pd_tool.core.types.advanced import Err
from marc_pd_tool.core.types.advanced import MatchResultType
from marc_pd_tool.core.types.advanced import Ok
from marc_pd_tool.core.types.advanced import QueryBuilder
from marc_pd_tool.core.types.advanced import Result
from marc_pd_tool.core.types.aliases import (
    BatchProcessingInfo as BatchProcessingInfoTuple,
)
from marc_pd_tool.core.types.aliases import AbbreviationDict
from marc_pd_tool.core.types.aliases import PatternDict
from marc_pd_tool.core.types.aliases import StemmerDict
from marc_pd_tool.core.types.aliases import StopwordDict
from marc_pd_tool.core.types.aliases import T

# New batch model
from marc_pd_tool.core.types.batch import BatchProcessingInfo
from marc_pd_tool.core.types.batch import DetectorConfig

# Note: Model classes should be imported directly from their modules,
# not through the types package, to avoid circular dependencies
from marc_pd_tool.core.types.json import JSONDict
from marc_pd_tool.core.types.json import JSONList
from marc_pd_tool.core.types.json import JSONPrimitive
from marc_pd_tool.core.types.json import JSONType

# New Pydantic models
from marc_pd_tool.core.types.models import CacheMetadata
from marc_pd_tool.core.types.models import CopyrightRecord
from marc_pd_tool.core.types.models import GenericTitleInfo
from marc_pd_tool.core.types.models import MatchResultData
from marc_pd_tool.core.types.models import SimilarityScores

# Interfaces - now all in protocols.py
from marc_pd_tool.core.types.protocols import AnalyzerProtocol
from marc_pd_tool.core.types.protocols import CSVRow
from marc_pd_tool.core.types.protocols import CSVWriter
from marc_pd_tool.core.types.protocols import CacheProtocol
from marc_pd_tool.core.types.protocols import ConfigProtocol
from marc_pd_tool.core.types.protocols import CopyrightLoaderProtocol
from marc_pd_tool.core.types.protocols import ExportAnalyzerProtocol
from marc_pd_tool.core.types.protocols import ExporterProtocol
from marc_pd_tool.core.types.protocols import GroundTruthAnalyzerProtocol
from marc_pd_tool.core.types.protocols import IndexProtocol
from marc_pd_tool.core.types.protocols import InvertedIndexProtocol
from marc_pd_tool.core.types.protocols import LoaderProtocol
from marc_pd_tool.core.types.protocols import MarcLoaderProtocol
from marc_pd_tool.core.types.protocols import MatcherProtocol
from marc_pd_tool.core.types.protocols import MultiFormatExporterProtocol
from marc_pd_tool.core.types.protocols import PersistentCacheProtocol
from marc_pd_tool.core.types.protocols import ProcessorProtocol
from marc_pd_tool.core.types.protocols import StemmerProtocol
from marc_pd_tool.core.types.protocols import StreamingAnalyzerProtocol
from marc_pd_tool.core.types.protocols import TextProcessorProtocol
from marc_pd_tool.core.types.protocols import ThresholdConfigProtocol

# Legacy TypedDicts (for backward compatibility during migration)
from marc_pd_tool.core.types.results import CacheMetadata as CacheMetadataDict
from marc_pd_tool.core.types.results import CopyrightRecordDict
from marc_pd_tool.core.types.results import GenericTitleInfoDict
from marc_pd_tool.core.types.results import MatchResultDict
from marc_pd_tool.core.types.results import SimilarityScoresDict
from marc_pd_tool.core.types.wordlists import Abbreviations
from marc_pd_tool.core.types.wordlists import TextFixes
from marc_pd_tool.core.types.wordlists import Wordlists

__all__ = [
    # Advanced types
    "Ok",
    "Err",
    "Result",
    "MatchResultType",
    "QueryBuilder",
    # Aliases
    "AbbreviationDict",
    "BatchProcessingInfoTuple",  # Legacy tuple version
    "BatchProcessingInfo",  # New Pydantic model
    "DetectorConfig",
    "PatternDict",
    "StemmerDict",
    "StopwordDict",
    "T",
    # JSON
    "JSONDict",
    "JSONList",
    "JSONPrimitive",
    "JSONType",
    # Protocols
    "CSVRow",
    "CSVWriter",
    "StemmerProtocol",
    # Loader Protocols
    "LoaderProtocol",
    "MarcLoaderProtocol",
    "CopyrightLoaderProtocol",
    # Processing Protocols
    "ProcessorProtocol",
    "TextProcessorProtocol",
    "MatcherProtocol",
    # Cache Protocols
    "CacheProtocol",
    "PersistentCacheProtocol",
    # Exporter Protocols
    "ExporterProtocol",
    "MultiFormatExporterProtocol",
    # Index Protocols
    "IndexProtocol",
    "InvertedIndexProtocol",
    # Configuration Protocols
    "ConfigProtocol",
    "ThresholdConfigProtocol",
    # API Component Protocols
    "ExportAnalyzerProtocol",
    "GroundTruthAnalyzerProtocol",
    "AnalyzerProtocol",
    "StreamingAnalyzerProtocol",
    # Legacy TypedDicts (deprecated)
    "CacheMetadataDict",
    "CopyrightRecordDict",
    "GenericTitleInfoDict",
    "MatchResultDict",
    "SimilarityScoresDict",
    # New Pydantic models
    "CacheMetadata",
    "CopyrightRecord",
    "GenericTitleInfo",
    "MatchResultData",
    "SimilarityScores",
    # Wordlists
    "Abbreviations",
    "TextFixes",
    "Wordlists",
]
