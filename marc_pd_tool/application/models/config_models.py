# marc_pd_tool/application/models/config_models.py

"""Pydantic models for configuration options"""

# Standard library imports

# Third party imports
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field


class AnalysisOptions(BaseModel):
    """Options for analyze_marc_file and analyze_marc_records API methods"""

    model_config = ConfigDict(extra="allow")  # Allow extra fields for flexibility

    min_year: int | None = None
    max_year: int | None = None
    us_only: bool = False
    year_tolerance: int = 1
    title_threshold: int = 40
    author_threshold: int = 30
    publisher_threshold: int | None = None
    early_exit_title: int = 95
    early_exit_author: int = 90
    early_exit_publisher: int | None = None
    score_everything_mode: bool = False
    lccn_support: bool = True
    fuzzy_ratio_threshold: int = 65
    num_processes: int | None = None
    batch_size: int = 100
    brute_force_missing_year: bool = False
    formats: list[str] = Field(default_factory=lambda: ["csv"])
    single_file: bool = False
    minimum_combined_score: int | None = None
    parallel_loading: bool = True  # Use parallel loading for copyright/renewal data

    def get[T](self, key: str, default: T | None = None) -> T | None:
        """Get option value with default

        Args:
            key: Option name
            default: Default value if not set

        Returns:
            Option value or default
        """
        return getattr(self, key, default)

    def to_dict(self) -> dict[str, object]:
        """Convert to dictionary

        Returns:
            Dictionary representation
        """
        return self.model_dump()


class ExportOptions(BaseModel):
    """Options for export_results API method"""

    model_config = ConfigDict()

    formats: list[str] = Field(default_factory=lambda: ["csv"])
    single_file: bool = False


# Note: ScoringWeights, GenericDetectorConfig, WordBasedConfig, and MatchingConfig
# are now imported from config/shared_models.py to avoid duplication
