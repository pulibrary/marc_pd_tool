# marc_pd_tool/application/models/batch_stats.py

"""Pydantic models for batch processing statistics"""

# Third party imports
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field


class ScoreRange(BaseModel):
    """Score range information for analysis"""

    model_config = ConfigDict()

    min: float = Field(..., description="Minimum score")
    max: float = Field(..., description="Maximum score")
    mean: float = Field(..., description="Mean score")
    median: float = Field(..., description="Median score")
    std_dev: float = Field(..., description="Standard deviation")


class ThresholdRecommendation(BaseModel):
    """Recommended thresholds based on analysis"""

    model_config = ConfigDict()

    title: float = Field(..., description="Recommended title threshold")
    author: float = Field(..., description="Recommended author threshold")
    combined: float = Field(..., description="Recommended combined threshold")


class BatchStats(BaseModel):
    """Statistics from processing a batch of MARC records"""

    model_config = ConfigDict()

    batch_id: int = Field(..., description="Batch identifier")
    marc_count: int = Field(0, description="Number of MARC records processed")
    registration_matches_found: int = Field(0, description="Number of registration matches")
    renewal_matches_found: int = Field(0, description="Number of renewal matches")
    total_comparisons: int = Field(0, description="Total comparisons made")
    us_records: int = Field(0, description="Number of US records")
    non_us_records: int = Field(0, description="Number of non-US records")
    unknown_country_records: int = Field(0, description="Records with unknown country")
    processing_time: float = Field(0.0, description="Processing time in seconds")
    skipped_no_year: int = Field(0, description="Records skipped due to missing year")
    skipped_out_of_range: int = Field(0, description="Records skipped due to year out of range")
    skipped_non_us: int = Field(0, description="Records skipped due to non-US classification")
    records_with_errors: int = Field(0, description="Records that had processing errors")

    def increment(self, field: str, value: int = 1) -> None:
        """Increment a statistic field

        Args:
            field: Field name to increment
            value: Amount to increment by
        """
        if hasattr(self, field):
            current = getattr(self, field)
            setattr(self, field, current + value)

    def to_dict(self) -> dict:
        """Convert to dictionary

        Returns:
            Dictionary representation
        """
        return self.model_dump()
