# marc_pd_tool/data/ground_truth.py

"""Data structures for ground truth analysis"""

# Standard library imports
from dataclasses import dataclass
from statistics import mean
from statistics import median
from statistics import stdev

# Local imports
from marc_pd_tool.data.publication import Publication


@dataclass(slots=True)
class GroundTruthPair:
    """Represents a verified match between MARC and copyright/renewal records"""

    marc_record: Publication
    copyright_record: Publication
    match_type: str  # "registration" or "renewal"
    lccn: str  # The normalized LCCN that matched

    def __post_init__(self) -> None:
        """Validate that this is indeed a matching pair"""
        if not self.marc_record.normalized_lccn:
            raise ValueError("MARC record must have normalized LCCN")
        if not self.copyright_record.normalized_lccn:
            raise ValueError("Copyright record must have normalized LCCN")
        if self.marc_record.normalized_lccn != self.copyright_record.normalized_lccn:
            raise ValueError("LCCN values must match")
        if self.match_type not in ("registration", "renewal"):
            raise ValueError("Match type must be 'registration' or 'renewal'")


@dataclass(slots=True)
class GroundTruthStats:
    """Statistics about extracted ground truth pairs"""

    total_marc_records: int
    marc_with_lccn: int
    total_copyright_records: int
    copyright_with_lccn: int
    total_renewal_records: int
    registration_matches: int
    renewal_matches: int
    unique_lccns_matched: int

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


@dataclass(slots=True)
class ScoreDistribution:
    """Statistical distribution of similarity scores for a field"""

    field_name: str
    scores: list[float]

    @property
    def mean_score(self) -> float:
        return mean(self.scores) if self.scores else 0.0

    @property
    def median_score(self) -> float:
        return median(self.scores) if self.scores else 0.0

    @property
    def std_dev(self) -> float:
        return stdev(self.scores) if len(self.scores) > 1 else 0.0

    @property
    def min_score(self) -> float:
        return min(self.scores) if self.scores else 0.0

    @property
    def max_score(self) -> float:
        return max(self.scores) if self.scores else 0.0

    @property
    def percentile_5(self) -> float:
        return self._percentile(5) if self.scores else 0.0

    @property
    def percentile_25(self) -> float:
        return self._percentile(25) if self.scores else 0.0

    @property
    def percentile_75(self) -> float:
        return self._percentile(75) if self.scores else 0.0

    @property
    def percentile_95(self) -> float:
        return self._percentile(95) if self.scores else 0.0

    def _percentile(self, p: int) -> float:
        """Calculate percentile of scores"""
        if not self.scores:
            return 0.0
        sorted_scores = sorted(self.scores)
        k = (len(sorted_scores) - 1) * (p / 100)
        f = int(k)
        c = k - f
        if f == len(sorted_scores) - 1:
            return sorted_scores[f]
        return sorted_scores[f] * (1 - c) + sorted_scores[f + 1] * c


@dataclass(slots=True)
class GroundTruthAnalysis:
    """Complete analysis of ground truth pairs"""

    total_pairs: int
    registration_pairs: int
    renewal_pairs: int
    title_distribution: ScoreDistribution
    author_distribution: ScoreDistribution
    publisher_distribution: ScoreDistribution
    combined_distribution: ScoreDistribution
    pairs_by_match_type: dict[str, list[GroundTruthPair]]
