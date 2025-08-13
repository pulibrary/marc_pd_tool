# marc_pd_tool/core/types/__init__.py

"""Type definitions for the MARC PD Tool

This package contains all type definitions, protocols, and type aliases
used throughout the codebase. These are pure type definitions with no
implementation logic.
"""

# Local imports
from marc_pd_tool.core.types.aliases import AbbreviationDict
from marc_pd_tool.core.types.aliases import BatchProcessingInfo
from marc_pd_tool.core.types.aliases import PatternDict
from marc_pd_tool.core.types.aliases import StemmerDict
from marc_pd_tool.core.types.aliases import StopwordDict
from marc_pd_tool.core.types.aliases import T

# Note: Model classes should be imported directly from their modules,
# not through the types package, to avoid circular dependencies
from marc_pd_tool.core.types.json import JSONDict
from marc_pd_tool.core.types.json import JSONList
from marc_pd_tool.core.types.json import JSONPrimitive
from marc_pd_tool.core.types.json import JSONType
from marc_pd_tool.core.types.protocols import CSVWriter
from marc_pd_tool.core.types.protocols import StemmerProtocol
from marc_pd_tool.core.types.results import CacheMetadata
from marc_pd_tool.core.types.results import CopyrightRecordDict
from marc_pd_tool.core.types.results import GenericTitleInfoDict
from marc_pd_tool.core.types.results import MatchResultDict
from marc_pd_tool.core.types.results import SimilarityScoresDict
from marc_pd_tool.core.types.wordlists import Abbreviations
from marc_pd_tool.core.types.wordlists import TextFixes
from marc_pd_tool.core.types.wordlists import Wordlists

__all__ = [
    # Aliases
    "AbbreviationDict",
    "BatchProcessingInfo",
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
    "CSVWriter",
    "StemmerProtocol",
    # Results
    "CacheMetadata",
    "CopyrightRecordDict",
    "GenericTitleInfoDict",
    "MatchResultDict",
    "SimilarityScoresDict",
    # Wordlists
    "Abbreviations",
    "TextFixes",
    "Wordlists",
]
