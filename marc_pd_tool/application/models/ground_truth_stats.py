# marc_pd_tool/application/models/ground_truth_stats.py

"""Data structures for ground truth analysis"""

# Third party imports
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import computed_field


class GroundTruthStats(BaseModel):
    """Statistics about extracted ground truth pairs"""

    model_config = ConfigDict()

    total_marc_records: int
    marc_with_lccn: int
    total_copyright_records: int = Field(default=0)
    copyright_with_lccn: int = Field(default=0)
    total_renewal_records: int = Field(default=0)
    registration_matches: int = Field(default=0)
    renewal_matches: int = Field(default=0)
    unique_lccns_matched: int = Field(default=0)
    unique_lccns: int = Field(default=0, description="Field for compatibility")

    @computed_field  # type: ignore[misc]
    @property
    def total_matches(self) -> int:
        return self.registration_matches + self.renewal_matches

    @computed_field  # type: ignore[misc]
    @property
    def marc_lccn_coverage(self) -> float:
        return (
            (self.marc_with_lccn / self.total_marc_records) * 100
            if self.total_marc_records > 0
            else 0.0
        )

    @computed_field  # type: ignore[misc]
    @property
    def copyright_lccn_coverage(self) -> float:
        return (
            (self.copyright_with_lccn / self.total_copyright_records) * 100
            if self.total_copyright_records > 0
            else 0.0
        )
