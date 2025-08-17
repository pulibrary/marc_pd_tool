# marc_pd_tool/core/types/batch.py

"""Batch processing type definitions using Pydantic models."""

# Third party imports
# Third-party imports
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field

# Configuration for batch models
BATCH_CONFIG = ConfigDict(strict=True, validate_assignment=True, frozen=True, extra="forbid")


class DetectorConfig(BaseModel):
    """Detector configuration for batch processing."""

    model_config = BATCH_CONFIG

    # Using dict for now since structure varies
    # Could be expanded to specific fields later
    settings: dict[str, int | bool] = Field(default_factory=dict)


class BatchProcessingInfo(BaseModel):
    """Information for processing a batch of MARC records.

    This replaces the complex tuple type with a proper model.
    """

    model_config = BATCH_CONFIG

    batch_id: int = Field(..., description="Batch identifier (1-based)")
    batch_path: str = Field(..., description="Path to pickled batch file")
    worker_cache_dir: str = Field(..., description="Worker cache directory")
    copyright_dir: str = Field(..., description="Copyright data directory")
    renewal_dir: str = Field(..., description="Renewal data directory")
    config_hash: str = Field(..., description="Configuration hash")
    detector_config: dict[str, int | bool] = Field(
        default_factory=dict, description="Detector settings"
    )
    total_batches: int = Field(..., ge=1, description="Total number of batches")

    # Thresholds
    title_threshold: int = Field(40, ge=0, le=100)
    author_threshold: int = Field(30, ge=0, le=100)
    publisher_threshold: int = Field(30, ge=0, le=100)
    year_tolerance: int = Field(1, ge=0)
    early_exit_title: int = Field(95, ge=0, le=100)
    early_exit_author: int = Field(90, ge=0, le=100)
    early_exit_publisher: int = Field(90, ge=0, le=100)

    # Options
    score_everything: bool = Field(False)
    minimum_combined_score: int | None = Field(None, ge=0, le=100)
    brute_force_missing_year: bool = Field(False)
    min_year: int | None = Field(None, ge=1450, le=2100)
    max_year: int | None = Field(None, ge=1450, le=2100)
    result_temp_dir: str = Field(..., description="Directory for result pickle files")

    def to_tuple(
        self,
    ) -> tuple[
        int,
        str,
        str,
        str,
        str,
        str,
        dict[str, int | bool],
        int,
        int,
        int,
        int,
        int,
        int,
        int,
        int,
        bool,
        int | None,
        bool,
        int | None,
        int | None,
        str,
    ]:
        """Convert to legacy tuple format for backward compatibility."""
        return (
            self.batch_id,
            self.batch_path,
            self.worker_cache_dir,
            self.copyright_dir,
            self.renewal_dir,
            self.config_hash,
            self.detector_config,
            self.total_batches,
            self.title_threshold,
            self.author_threshold,
            self.publisher_threshold,
            self.year_tolerance,
            self.early_exit_title,
            self.early_exit_author,
            self.early_exit_publisher,
            self.score_everything,
            self.minimum_combined_score,
            self.brute_force_missing_year,
            self.min_year,
            self.max_year,
            self.result_temp_dir,
        )

    @classmethod
    def from_tuple(
        cls,
        data: tuple[
            int,
            str,
            str,
            str,
            str,
            str,
            dict[str, int | bool],
            int,
            int,
            int,
            int,
            int,
            int,
            int,
            int,
            bool,
            int | None,
            bool,
            int | None,
            int | None,
            str,
        ],
    ) -> "BatchProcessingInfo":
        """Create from legacy tuple format."""
        return cls(
            batch_id=data[0],
            batch_path=data[1],
            worker_cache_dir=data[2],
            copyright_dir=data[3],
            renewal_dir=data[4],
            config_hash=data[5],
            detector_config=data[6],
            total_batches=data[7],
            title_threshold=data[8],
            author_threshold=data[9],
            publisher_threshold=data[10],
            year_tolerance=data[11],
            early_exit_title=data[12],
            early_exit_author=data[13],
            early_exit_publisher=data[14],
            score_everything=data[15],
            minimum_combined_score=data[16],
            brute_force_missing_year=data[17],
            min_year=data[18],
            max_year=data[19],
            result_temp_dir=data[20],
        )


__all__ = ["DetectorConfig", "BatchProcessingInfo"]
