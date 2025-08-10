# marc_pd_tool/data/ground_truth.py

"""Data structures for ground truth analysis"""

# Standard library imports
from dataclasses import dataclass


@dataclass(slots=True)
class GroundTruthStats:
    """Statistics about extracted ground truth pairs"""

    total_marc_records: int
    marc_with_lccn: int
    total_copyright_records: int = 0
    copyright_with_lccn: int = 0
    total_renewal_records: int = 0
    registration_matches: int = 0
    renewal_matches: int = 0
    unique_lccns_matched: int = 0
    unique_lccns: int = 0  # Add this field for compatibility

    @property
    def total_matches(self) -> int:
        return self.registration_matches + self.renewal_matches

    @property
    def marc_lccn_coverage(self) -> float:
        return (
            (self.marc_with_lccn / self.total_marc_records) * 100
            if self.total_marc_records > 0
            else 0.0
        )

    @property
    def copyright_lccn_coverage(self) -> float:
        return (
            (self.copyright_with_lccn / self.total_copyright_records) * 100
            if self.total_copyright_records > 0
            else 0.0
        )
