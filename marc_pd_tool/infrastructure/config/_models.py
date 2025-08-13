# marc_pd_tool/infrastructure/config/_models.py

"""Pydantic models for configuration with validation"""

# Standard library imports
from pathlib import Path

# Third party imports
from pydantic import BaseModel
from pydantic import Field
from pydantic import field_validator

# Local imports
from marc_pd_tool.core.types.json import JSONDict
from marc_pd_tool.infrastructure.config._shared_models import GenericDetectorConfig
from marc_pd_tool.infrastructure.config._shared_models import MatchingConfig


class ProcessingConfig(BaseModel):
    """Processing configuration with validation"""

    batch_size: int = Field(100, gt=0, description="Records per batch")
    max_workers: int | None = Field(None, ge=1, description="Number of worker processes")
    score_everything_mode: bool = Field(
        False, description="Find best match regardless of thresholds"
    )

    @field_validator("max_workers")
    @classmethod
    def validate_workers(cls, v: int | None) -> int | None:
        """Ensure max_workers is reasonable"""
        if v is not None and v > 128:  # Arbitrary but reasonable upper limit
            raise ValueError("max_workers should not exceed 128")
        return v


class FilteringConfig(BaseModel):
    """Filtering configuration"""

    min_year: int | None = Field(None, description="Minimum publication year")
    max_year: int | None = Field(None, description="Maximum publication year")
    us_only: bool = Field(False, description="Process only US publications")
    brute_force_missing_year: bool = Field(False, description="Process records without year data")

    @field_validator("min_year", "max_year")
    @classmethod
    def validate_year(cls, v: int | None) -> int | None:
        """Validate year is reasonable"""
        if v is not None and (v < 1000 or v > 3000):
            raise ValueError(f"Year {v} is outside reasonable range (1000-3000)")
        return v


class OutputConfig(BaseModel):
    """Output configuration"""

    single_file: bool = Field(False, description="Save all results to single file")


class CachingConfig(BaseModel):
    """Caching configuration"""

    cache_dir: str = Field(".marcpd_cache", description="Directory for cache files")
    force_refresh: bool = Field(False, description="Force cache refresh")
    no_cache: bool = Field(
        False, description="Disable caching"
    )  # Will rename to disable_cache later


class LoggingConfig(BaseModel):
    """Logging configuration"""

    debug: bool = Field(False, description="Enable debug logging")
    log_file: str | None = Field(None, description="Log file path")


class ThresholdsConfig(BaseModel):
    """Matching thresholds configuration"""

    title: int = Field(40, ge=0, le=100, description="Title similarity threshold")
    author: int = Field(30, ge=0, le=100, description="Author similarity threshold")
    publisher: int = Field(60, ge=0, le=100, description="Publisher similarity threshold")
    early_exit_title: int = Field(95, ge=0, le=100, description="Early exit title threshold")
    early_exit_author: int = Field(90, ge=0, le=100, description="Early exit author threshold")
    early_exit_publisher: int = Field(
        85, ge=0, le=100, description="Early exit publisher threshold"
    )
    year_tolerance: int = Field(1, ge=0, le=10, description="Year matching tolerance")
    minimum_combined_score: int = Field(40, ge=0, le=100, description="Minimum combined score")


# Note: WordBasedConfig, MatchingConfig, and GenericDetectorConfig
# are now imported from shared_models.py


class ScoringWeightsConfig(BaseModel):
    """Scoring weights for different scenarios"""

    normal_with_publisher: dict[str, float] = Field(
        default={"title": 0.6, "author": 0.25, "publisher": 0.15}
    )
    generic_with_publisher: dict[str, float] = Field(
        default={"title": 0.3, "author": 0.45, "publisher": 0.25}
    )
    normal_no_publisher: dict[str, float] = Field(default={"title": 0.7, "author": 0.3})
    generic_no_publisher: dict[str, float] = Field(default={"title": 0.4, "author": 0.6})

    @field_validator(
        "normal_with_publisher",
        "generic_with_publisher",
        "normal_no_publisher",
        "generic_no_publisher",
    )
    @classmethod
    def validate_weights(cls, v: dict[str, float]) -> dict[str, float]:
        """Ensure weights sum to 1.0"""
        total = sum(v.values())
        if not (0.99 <= total <= 1.01):  # Allow small floating point errors
            raise ValueError(f"Weights must sum to 1.0, got {total}")
        return v


class AppConfig(BaseModel):
    """Root application configuration model"""

    processing: ProcessingConfig = Field(default_factory=ProcessingConfig)
    filtering: FilteringConfig = Field(default_factory=FilteringConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    caching: CachingConfig = Field(default_factory=CachingConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    default_thresholds: ThresholdsConfig = Field(default_factory=ThresholdsConfig)
    matching: MatchingConfig = Field(default_factory=MatchingConfig)
    generic_title_detector: GenericDetectorConfig = Field(default_factory=GenericDetectorConfig)
    scoring_weights: ScoringWeightsConfig = Field(default_factory=ScoringWeightsConfig)

    @classmethod
    def load(cls, config_path: Path | str | None = None) -> "AppConfig":
        """Load configuration from JSON file with defaults

        Args:
            config_path: Path to configuration JSON file

        Returns:
            Validated AppConfig instance
        """
        # Standard library imports
        import json

        # Convert to Path if string
        if isinstance(config_path, str):
            config_path = Path(config_path)

        # If no path provided, try to find config.json in current directory
        if config_path is None:
            config_path = Path("config.json")
            if not config_path.exists():
                # Return default config
                return cls()

        # Load and validate config file
        if config_path and config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return cls.model_validate(data)
            except Exception as e:
                # Log warning and return defaults
                # Standard library imports
                import logging

                logging.getLogger(__name__).warning(
                    f"Failed to load config from {config_path}: {e}. Using defaults."
                )
                return cls()

        # Return default config
        return cls()

    def to_dict(self) -> JSONDict:
        """Convert to dictionary for backward compatibility"""
        return self.model_dump()

    def get_threshold(self, name: str) -> int:
        """Get a threshold value by name for backward compatibility

        Args:
            name: Threshold name

        Returns:
            Threshold value or 80 as default
        """
        thresholds = self.default_thresholds.model_dump()
        return thresholds.get(name, 80)
