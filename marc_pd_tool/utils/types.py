# marc_pd_tool/utils/types.py

"""Centralized type definitions for the MARC PD Tool

This module contains all custom type definitions used throughout the codebase,
helping to avoid circular imports and maintain consistency.
"""

# Standard library imports
from typing import Optional
from typing import Protocol
from typing import TYPE_CHECKING
from typing import TypeVar
from typing import TypedDict

if TYPE_CHECKING:
    # Local imports
    from marc_pd_tool.data.publication import MatchResult
    from marc_pd_tool.data.publication import Publication


class CSVWriter(Protocol):
    """Protocol for CSV writer objects"""

    def writerow(self, row: list[str | int | float | bool | None]) -> None: ...
    def writerows(self, rows: list[list[str | int | float | bool | None]]) -> None: ...


class StemmerProtocol(Protocol):
    """Protocol for Stemmer objects from PyStemmer"""

    def stemWord(self, word: str) -> str: ...
    def stemWords(self, words: list[str]) -> list[str]: ...


# Define a generic type for JSON data
JSONPrimitive = str | int | float | bool | None
JSONType = dict[str, "JSONType"] | list["JSONType"] | JSONPrimitive

# "Wrapper" types that at least give a hint at the outermost structure
JSONDict = dict[str, JSONType]


# Domain-specific dictionaries that add clarity
StopwordDict = dict[str, list[str]]  # Category -> stopwords
PatternDict = dict[str, list[str]]  # Pattern type -> patterns
AbbreviationDict = dict[str, str]  # Abbreviation -> expansion
StemmerDict = dict[str, StemmerProtocol]  # Language -> Stemmer object


# Match result type aliases (from word_matching_engine)
# Note: These are defined as TypedDicts below for better type safety


# API Options types
class AnalysisOptions(TypedDict, total=False):
    """Options for analyze_marc_file and analyze_marc_records API methods"""

    min_year: int | None
    max_year: int | None
    us_only: bool
    year_tolerance: int
    title_threshold: int
    author_threshold: int
    early_exit_title: int
    early_exit_author: int
    score_everything_mode: bool
    lccn_support: bool
    fuzzy_ratio_threshold: int
    num_processes: int
    batch_size: int
    brute_force_missing_year: bool
    format: str  # 'csv' | 'json' | 'xlsx'
    single_file: bool


class ExportOptions(TypedDict, total=False):
    """Options for export_results API method"""

    format: str  # 'csv' | 'json' | 'xlsx'
    single_file: bool


# Configuration types
class ScoringWeights(TypedDict, total=False):
    """Type for scoring weight configurations"""

    title: float
    author: float
    publisher: float


class GenericDetectorConfig(TypedDict):
    """Type for generic detector configuration"""

    frequency_threshold: int


class WordBasedConfig(TypedDict):
    """Type for word-based matching configuration"""

    default_language: str
    enable_stemming: bool
    enable_abbreviation_expansion: bool


class MatchingConfig(TypedDict, total=False):
    """Type for matching configuration"""

    word_based: WordBasedConfig


class Config(TypedDict):
    """Type for main configuration"""

    scoring_weights: dict[str, ScoringWeights]
    default_thresholds: dict[str, int]
    generic_title_detector: GenericDetectorConfig
    matching: MatchingConfig


# Wordlist types
class Abbreviations(TypedDict):
    """Type for abbreviations section"""

    bibliographic: dict[str, str]


class TextFixes(TypedDict):
    """Type for text fixes section"""

    unicode_corrections: dict[str, str]


class Wordlists(TypedDict):
    """Type for wordlists configuration"""

    abbreviations: Abbreviations
    stopwords: dict[str, list[str]]
    patterns: dict[str, list[str]]
    text_fixes: TextFixes


# Publication to_dict() output type (defined before MatchResultDict uses it)


# Match result types
class SimilarityScoresDict(TypedDict):
    """Similarity scores for different fields"""

    title: float
    author: float
    publisher: float
    combined: float


class GenericTitleInfoDict(TypedDict):
    """Generic title detection information"""

    has_generic_title: bool
    marc_title_is_generic: bool
    copyright_title_is_generic: bool
    marc_detection_reason: str
    copyright_detection_reason: str


class CopyrightRecordDict(TypedDict):
    """Copyright record data in match result"""

    title: str
    author: str
    year: int | None
    publisher: str
    source_id: str
    pub_date: str
    full_text: str


class MatchResultDict(TypedDict):
    """Type-safe match result from matching engine"""

    match: Optional["MatchResult"]
    copyright_record: CopyrightRecordDict
    similarity_scores: SimilarityScoresDict
    is_lccn_match: bool
    generic_title_info: Optional[GenericTitleInfoDict]


# Cache metadata types
class CacheMetadata(TypedDict):
    """Type for cache metadata"""

    version: str
    source_files: list[str]
    source_mtimes: list[float]
    cache_time: float
    additional_deps: dict[str, JSONType]


# Batch processing types


# Analysis types
class ScoreRange(TypedDict):
    """Type for score range information"""

    min: float
    max: float
    mean: float
    median: float
    std_dev: float


class ThresholdRecommendation(TypedDict):
    """Type for threshold recommendations"""

    title: float
    author: float
    combined: float


# Batch processing info type
BatchProcessingInfo = tuple[
    int,  # batch_id (i + 1)
    list["Publication"],  # batch
    str,  # worker_cache_dir
    str,  # copyright_dir
    str,  # renewal_dir
    str,  # config_hash
    dict[str, int | bool],  # detector_config
    int,  # total_batches
    int,  # title_threshold
    int,  # author_threshold
    int,  # year_tolerance
    int,  # early_exit_title
    int,  # early_exit_author
    bool,  # score_everything
    int,  # minimum_combined_score
    bool,  # brute_force_missing_year
]

# Generic type variables
T = TypeVar("T")


# Batch processing result types
class BatchStats(TypedDict):
    """Statistics from processing a batch"""

    batch_id: int
    marc_count: int
    registration_matches_found: int
    renewal_matches_found: int
    total_comparisons: int
    us_records: int
    non_us_records: int
    unknown_country_records: int
