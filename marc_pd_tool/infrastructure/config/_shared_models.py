# marc_pd_tool/infrastructure/config/_shared_models.py

"""Shared configuration models used by both config and API"""

# Third party imports
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field


class ScoringWeights(BaseModel):
    """Scoring weight configurations

    Used for calculating combined similarity scores.
    """

    model_config = ConfigDict()

    title: float = Field(0.5, ge=0.0, le=1.0)
    author: float = Field(0.3, ge=0.0, le=1.0)
    publisher: float = Field(0.2, ge=0.0, le=1.0)


class WordBasedConfig(BaseModel):
    """Word-based matching configuration

    Controls how text is processed for matching.
    """

    model_config = ConfigDict()

    default_language: str = "eng"
    enable_stemming: bool = True
    enable_abbreviation_expansion: bool = True
    stopword_removal: bool = True


class GenericDetectorConfig(BaseModel):
    """Generic title detector configuration

    Controls how generic titles are detected.
    """

    model_config = ConfigDict()

    # Use lower default (10) as that's what the code expects
    frequency_threshold: int = Field(10, ge=1, description="Minimum occurrences for generic title")
    enable_pattern_matching: bool = Field(True, description="Enable pattern-based detection")
    enable_frequency_analysis: bool = Field(True, description="Enable frequency-based detection")
    disable_generic_detection: bool = Field(
        False, description="Disable generic title detection entirely"
    )


class MatchingConfig(BaseModel):
    """Matching engine configuration

    Controls the matching process.
    """

    model_config = ConfigDict()

    word_based: WordBasedConfig = Field(default_factory=WordBasedConfig)
    enable_lccn_matching: bool = Field(True, description="Enable LCCN-based matching")
    enable_publisher_matching: bool = Field(True, description="Enable publisher matching")
