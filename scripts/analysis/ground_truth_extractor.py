# scripts/analysis/ground_truth_extractor.py

"""Ground truth extraction for LCCN-matched publication pairs"""

# Standard library imports
from collections import defaultdict
from dataclasses import dataclass
from logging import getLogger

# Local imports
from marc_pd_tool.data.publication import Publication

logger = getLogger(__name__)


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


class GroundTruthExtractor:
    """Extracts LCCN-verified ground truth pairs for algorithm validation and optimization"""

    def __init__(self) -> None:
        self.logger = getLogger(self.__class__.__name__)

    def extract_ground_truth_pairs(
        self,
        marc_batches: list[list[Publication]],
        copyright_publications: list[Publication],
        renewal_publications: list[Publication] | None = None,
    ) -> tuple[list[GroundTruthPair], GroundTruthStats]:
        """Extract all LCCN-matched pairs from the datasets

        Args:
            marc_batches: List of MARC publication batches
            copyright_publications: List of copyright registration publications
            renewal_publications: Optional list of renewal publications

        Returns:
            Tuple of (ground_truth_pairs, statistics)
        """
        if renewal_publications is None:
            renewal_publications = []

        self.logger.info("Starting ground truth extraction based on LCCN matching")

        # Flatten MARC batches
        marc_records = []
        for batch in marc_batches:
            marc_records.extend(batch)

        # Build LCCN indexes for fast lookup
        copyright_lccn_index = self._build_lccn_index(copyright_publications)
        renewal_lccn_index = (
            self._build_lccn_index(renewal_publications) if renewal_publications else {}
        )

        self.logger.info(
            f"Built LCCN indexes: {len(copyright_lccn_index)} copyright, {len(renewal_lccn_index)} renewal"
        )

        # Extract matching pairs
        ground_truth_pairs = []

        # Track statistics
        marc_with_lccn = 0
        registration_matches = 0
        renewal_matches = 0
        matched_lccns = set()

        for marc_record in marc_records:
            if not marc_record.normalized_lccn:
                continue

            marc_with_lccn += 1
            lccn = marc_record.normalized_lccn

            # Check for copyright registration matches
            if lccn in copyright_lccn_index:
                for copyright_record in copyright_lccn_index[lccn]:
                    try:
                        pair = GroundTruthPair(
                            marc_record=marc_record,
                            copyright_record=copyright_record,
                            match_type="registration",
                            lccn=lccn,
                        )
                        ground_truth_pairs.append(pair)
                        registration_matches += 1
                        matched_lccns.add(lccn)
                    except ValueError as e:
                        self.logger.warning(f"Invalid ground truth pair: {e}")

            # Check for renewal matches
            if lccn in renewal_lccn_index:
                for renewal_record in renewal_lccn_index[lccn]:
                    try:
                        pair = GroundTruthPair(
                            marc_record=marc_record,
                            copyright_record=renewal_record,
                            match_type="renewal",
                            lccn=lccn,
                        )
                        ground_truth_pairs.append(pair)
                        renewal_matches += 1
                        matched_lccns.add(lccn)
                    except ValueError as e:
                        self.logger.warning(f"Invalid ground truth pair: {e}")

        # Compile statistics
        stats = GroundTruthStats(
            total_marc_records=len(marc_records),
            marc_with_lccn=marc_with_lccn,
            total_copyright_records=len(copyright_publications),
            copyright_with_lccn=len(copyright_lccn_index),
            total_renewal_records=len(renewal_publications),
            registration_matches=registration_matches,
            renewal_matches=renewal_matches,
            unique_lccns_matched=len(matched_lccns),
        )

        self.logger.info(f"Ground truth extraction complete:")
        self.logger.info(
            f"  MARC records with LCCN: {marc_with_lccn:,} ({stats.marc_lccn_coverage:.1f}%)"
        )
        self.logger.info(
            f"  Copyright records with LCCN: {len(copyright_lccn_index):,} ({stats.copyright_lccn_coverage:.1f}%)"
        )
        self.logger.info(f"  Registration matches: {registration_matches:,}")
        self.logger.info(f"  Renewal matches: {renewal_matches:,}")
        self.logger.info(f"  Total ground truth pairs: {len(ground_truth_pairs):,}")
        self.logger.info(f"  Unique LCCNs matched: {len(matched_lccns):,}")

        return ground_truth_pairs, stats

    def _build_lccn_index(self, publications: list[Publication]) -> dict[str, list[Publication]]:
        """Build an index of publications by normalized LCCN for fast lookup

        Args:
            publications: List of publications to index

        Returns:
            Dictionary mapping normalized LCCN to list of publications
        """
        index = defaultdict(list)

        for pub in publications:
            if pub.normalized_lccn:
                index[pub.normalized_lccn].append(pub)

        return dict(index)

    def filter_by_lccn_prefix(
        self, ground_truth_pairs: list[GroundTruthPair], prefix: str
    ) -> list[GroundTruthPair]:
        """Filter ground truth pairs by LCCN prefix

        Args:
            ground_truth_pairs: List of ground truth pairs
            prefix: LCCN prefix to filter by (e.g., 'n' for monographs)

        Returns:
            Filtered list of ground truth pairs
        """
        # Local imports
        from marc_pd_tool.utils.text_utils import extract_lccn_prefix

        filtered_pairs = []
        for pair in ground_truth_pairs:
            if extract_lccn_prefix(pair.lccn) == prefix:
                filtered_pairs.append(pair)

        self.logger.info(f"Filtered to {len(filtered_pairs)} pairs with LCCN prefix '{prefix}'")
        return filtered_pairs

    def filter_by_year_range(
        self,
        ground_truth_pairs: list[GroundTruthPair],
        min_year: int | None = None,
        max_year: int | None = None,
    ) -> list[GroundTruthPair]:
        """Filter ground truth pairs by publication year range

        Args:
            ground_truth_pairs: List of ground truth pairs
            min_year: Minimum publication year (inclusive)
            max_year: Maximum publication year (inclusive)

        Returns:
            Filtered list of ground truth pairs
        """
        filtered_pairs = []

        for pair in ground_truth_pairs:
            marc_year = pair.marc_record.year
            copyright_year = pair.copyright_record.year

            # Use MARC year if available, otherwise copyright year
            year = marc_year if marc_year else copyright_year

            if year is None:
                continue  # Skip records without year information

            if min_year is not None and year < min_year:
                continue
            if max_year is not None and year > max_year:
                continue

            filtered_pairs.append(pair)

        year_filter_desc = []
        if min_year is not None:
            year_filter_desc.append(f"≥{min_year}")
        if max_year is not None:
            year_filter_desc.append(f"≤{max_year}")
        filter_desc = " and ".join(year_filter_desc) if year_filter_desc else "all years"

        self.logger.info(f"Filtered to {len(filtered_pairs)} pairs with years {filter_desc}")
        return filtered_pairs

    def get_coverage_report(self, stats: GroundTruthStats) -> str:
        """Generate a human-readable coverage report

        Args:
            stats: Ground truth statistics

        Returns:
            Formatted coverage report string
        """
        report = []
        report.append("LCCN Ground Truth Coverage Report")
        report.append("=" * 40)
        report.append(f"MARC Records:")
        report.append(f"  Total: {stats.total_marc_records:,}")
        report.append(f"  With LCCN: {stats.marc_with_lccn:,} ({stats.marc_lccn_coverage:.1f}%)")
        report.append(f"")
        report.append(f"Copyright Registration Records:")
        report.append(f"  Total: {stats.total_copyright_records:,}")
        report.append(
            f"  With LCCN: {stats.copyright_with_lccn:,} ({stats.copyright_lccn_coverage:.1f}%)"
        )
        report.append(f"")
        report.append(f"Renewal Records:")
        report.append(f"  Total: {stats.total_renewal_records:,}")
        report.append(f"")
        report.append(f"Ground Truth Matches:")
        report.append(f"  Registration matches: {stats.registration_matches:,}")
        report.append(f"  Renewal matches: {stats.renewal_matches:,}")
        report.append(f"  Total matches: {stats.total_matches:,}")
        report.append(f"  Unique LCCNs: {stats.unique_lccns_matched:,}")

        if stats.marc_with_lccn > 0:
            match_rate = (stats.total_matches / stats.marc_with_lccn) * 100
            report.append(f"  Match rate: {match_rate:.1f}% of MARC records with LCCN")

        return "\n".join(report)
