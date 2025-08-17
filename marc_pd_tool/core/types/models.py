# marc_pd_tool/core/types/models.py

"""Pydantic models for result types using modern Python 3.13 features."""

# Standard library imports
from typing import TYPE_CHECKING

# Third party imports
# Third-party imports
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field

# Local imports
from marc_pd_tool.core.types.json import JSONType

if TYPE_CHECKING:
    # Local imports
    from marc_pd_tool.core.domain.match_result import MatchResult

# Base configuration for result models
RESULT_MODEL_CONFIG = ConfigDict(
    strict=True,
    validate_assignment=True,
    frozen=True,
    extra="forbid",
    str_strip_whitespace=True,
    validate_default=True,
)


class SimilarityScores(BaseModel):
    """Similarity scores for different fields."""

    model_config = RESULT_MODEL_CONFIG

    title: float = Field(ge=0.0, le=100.0)
    author: float = Field(ge=0.0, le=100.0)
    publisher: float = Field(ge=0.0, le=100.0)
    combined: float = Field(ge=0.0, le=100.0)


class GenericTitleInfo(BaseModel):
    """Generic title detection information."""

    model_config = RESULT_MODEL_CONFIG

    has_generic_title: bool
    marc_title_is_generic: bool
    copyright_title_is_generic: bool
    marc_detection_reason: str = Field(min_length=1)
    copyright_detection_reason: str = Field(min_length=1)


class CopyrightRecord(BaseModel):
    """Copyright record data in match result."""

    model_config = RESULT_MODEL_CONFIG

    title: str = Field(min_length=1)
    author: str = Field(default="")
    year: int | None = Field(None, ge=1900, le=2100)
    publisher: str = Field(default="")
    source_id: str = Field(min_length=1)
    pub_date: str = Field(default="")
    full_text: str = Field(default="")
    # Normalized versions for analysis
    normalized_title: str = Field(min_length=1)
    normalized_author: str = Field(default="")
    normalized_publisher: str = Field(default="")


class MatchResultData(BaseModel):
    """Type-safe match result from matching engine."""

    model_config = RESULT_MODEL_CONFIG.copy()
    model_config["arbitrary_types_allowed"] = True  # For MatchResult type

    match: "MatchResult | None"
    copyright_record: CopyrightRecord
    similarity_scores: SimilarityScores
    is_lccn_match: bool
    generic_title_info: GenericTitleInfo | None = None


class CacheMetadata(BaseModel):
    """Type for cache metadata."""

    model_config = RESULT_MODEL_CONFIG

    version: str = Field(min_length=1)
    source_files: list[str] = Field(min_length=1)
    source_mtimes: list[float] = Field(min_length=1)
    cache_time: float = Field(gt=0)
    additional_deps: dict[str, JSONType] = Field(default_factory=dict)


__all__ = [
    "SimilarityScores",
    "GenericTitleInfo",
    "CopyrightRecord",
    "MatchResultData",
    "CacheMetadata",
]
