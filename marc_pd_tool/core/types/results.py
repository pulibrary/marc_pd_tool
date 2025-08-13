# marc_pd_tool/core/types/results.py

"""Result-related TypedDict definitions"""

# Standard library imports
from typing import Optional
from typing import TYPE_CHECKING
from typing import TypedDict

# Local imports
from marc_pd_tool.core.types.json import JSONType

if TYPE_CHECKING:
    # Local imports
    from marc_pd_tool.core.domain.match_result import MatchResult


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
    # Normalized versions for analysis
    normalized_title: str
    normalized_author: str
    normalized_publisher: str


class MatchResultDict(TypedDict):
    """Type-safe match result from matching engine"""

    match: Optional["MatchResult"]
    copyright_record: CopyrightRecordDict
    similarity_scores: SimilarityScoresDict
    is_lccn_match: bool
    generic_title_info: Optional[GenericTitleInfoDict]


class CacheMetadata(TypedDict):
    """Type for cache metadata"""

    version: str
    source_files: list[str]
    source_mtimes: list[float]
    cache_time: float
    additional_deps: dict[str, "JSONType"]


__all__ = [
    "SimilarityScoresDict",
    "GenericTitleInfoDict",
    "CopyrightRecordDict",
    "MatchResultDict",
    "CacheMetadata",
]
