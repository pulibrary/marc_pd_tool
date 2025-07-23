# scripts/analysis/score_analyzer.py

"""Similarity score analysis for ground truth pairs"""

# Standard library imports
from collections import defaultdict
from dataclasses import dataclass
from logging import getLogger
from statistics import mean
from statistics import median
from statistics import stdev
from typing import cast

# Local imports
from marc_pd_tool.data.publication import Publication
from marc_pd_tool.processing.matching_engine import DataMatcher
from marc_pd_tool.processing.text_processing import GenericTitleDetector
from marc_pd_tool.utils.types import MatchResultDict

# Local folder imports
from .ground_truth_extractor import GroundTruthPair

logger = getLogger(__name__)


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

    def get_recommended_thresholds(self, percentile: int = 5) -> dict[str, float]:
        """Get recommended thresholds based on percentile of ground truth scores

        Args:
            percentile: Percentile to use (default 5th percentile for conservative thresholds)

        Returns:
            Dictionary with recommended thresholds for each field
        """
        thresholds = {}

        if self.title_distribution.scores:
            thresholds["title"] = self.title_distribution._percentile(percentile)

        if self.author_distribution.scores:
            thresholds["author"] = self.author_distribution._percentile(percentile)

        if self.publisher_distribution.scores:
            thresholds["publisher"] = self.publisher_distribution._percentile(percentile)

        if self.combined_distribution.scores:
            thresholds["combined"] = self.combined_distribution._percentile(percentile)

        return thresholds


class ScoreAnalyzer:
    """Analyzes similarity score distributions for ground truth pairs"""

    def __init__(self, matcher: DataMatcher | None = None):
        self.logger = getLogger(self.__class__.__name__)
        self.matcher = matcher or DataMatcher()
        self.generic_detector = GenericTitleDetector()

    def analyze_ground_truth_scores(
        self, ground_truth_pairs: list[GroundTruthPair]
    ) -> GroundTruthAnalysis:
        """Analyze similarity score distributions for ground truth pairs

        Args:
            ground_truth_pairs: List of verified ground truth pairs

        Returns:
            Complete analysis with score distributions and statistics
        """
        self.logger.info(
            f"Analyzing similarity scores for {len(ground_truth_pairs)} ground truth pairs"
        )

        # Collect scores for each field
        title_scores = []
        author_scores = []
        publisher_scores = []
        combined_scores = []

        # Group pairs by match type
        pairs_by_type = defaultdict(list)

        for pair in ground_truth_pairs:
            pairs_by_type[pair.match_type].append(pair)

            # Calculate similarity scores using word-based matching
            # (excluding LCCN matching to get actual text similarity)
            match_result = self._calculate_text_similarity(pair.marc_record, pair.copyright_record)

            if match_result:
                scores = match_result["similarity_scores"]
                # Type check - scores should be a dict
                if isinstance(scores, dict):
                    title_scores.append(scores.get("title", 0.0))
                    author_scores.append(scores.get("author", 0.0))
                    publisher_scores.append(scores.get("publisher", 0.0))
                    combined_scores.append(scores.get("combined", 0.0))

        # Create distributions
        title_dist = ScoreDistribution("title", title_scores)
        author_dist = ScoreDistribution("author", author_scores)
        publisher_dist = ScoreDistribution("publisher", publisher_scores)
        combined_dist = ScoreDistribution("combined", combined_scores)

        # Count pairs by type
        registration_pairs = len(pairs_by_type["registration"])
        renewal_pairs = len(pairs_by_type["renewal"])

        analysis = GroundTruthAnalysis(
            total_pairs=len(ground_truth_pairs),
            registration_pairs=registration_pairs,
            renewal_pairs=renewal_pairs,
            title_distribution=title_dist,
            author_distribution=author_dist,
            publisher_distribution=publisher_dist,
            combined_distribution=combined_dist,
            pairs_by_match_type=dict(pairs_by_type),
        )

        self.logger.info(f"Analysis complete:")
        self.logger.info(f"  Registration pairs: {registration_pairs}")
        self.logger.info(f"  Renewal pairs: {renewal_pairs}")
        self.logger.info(
            f"  Title score range: {title_dist.min_score:.1f} - {title_dist.max_score:.1f}"
        )
        self.logger.info(
            f"  Author score range: {author_dist.min_score:.1f} - {author_dist.max_score:.1f}"
        )
        self.logger.info(
            f"  Publisher score range: {publisher_dist.min_score:.1f} - {publisher_dist.max_score:.1f}"
        )

        return analysis

    def _calculate_text_similarity(
        self, marc_pub: Publication, copyright_pub: Publication
    ) -> MatchResultDict | None:
        """Calculate similarity scores excluding LCCN matching

        This temporarily clears LCCN fields to force text-based matching
        """
        # Store original LCCN values
        marc_lccn = marc_pub.normalized_lccn
        copyright_lccn = copyright_pub.normalized_lccn

        try:
            # Temporarily clear LCCN to force text matching
            marc_pub.normalized_lccn = ""
            copyright_pub.normalized_lccn = ""

            # Calculate text-based similarity using ignore_thresholds to get actual scores
            match_result = self.matcher.find_best_match_ignore_thresholds(
                marc_pub,
                [copyright_pub],
                year_tolerance=10,  # Liberal year tolerance for analysis
                early_exit_title=100,  # No early exit
                early_exit_author=100,  # No early exit
                generic_detector=self.generic_detector,
            )

            return match_result

        finally:
            # Restore original LCCN values
            marc_pub.normalized_lccn = marc_lccn
            copyright_pub.normalized_lccn = copyright_lccn

    def generate_analysis_report(self, analysis: GroundTruthAnalysis) -> str:
        """Generate detailed analysis report

        Args:
            analysis: Ground truth analysis results

        Returns:
            Formatted analysis report
        """
        report = []
        report.append("LCCN Ground Truth Similarity Score Analysis")
        report.append("=" * 50)
        report.append(f"Total ground truth pairs analyzed: {analysis.total_pairs:,}")
        report.append(f"  Registration pairs: {analysis.registration_pairs:,}")
        report.append(f"  Renewal pairs: {analysis.renewal_pairs:,}")
        report.append("")

        # Title scores
        report.append("TITLE Similarity Scores:")
        report.append("-" * 25)
        self._add_distribution_stats(report, analysis.title_distribution)
        report.append("")

        # Author scores
        report.append("AUTHOR Similarity Scores:")
        report.append("-" * 26)
        self._add_distribution_stats(report, analysis.author_distribution)
        report.append("")

        # Publisher scores
        report.append("PUBLISHER Similarity Scores:")
        report.append("-" * 29)
        self._add_distribution_stats(report, analysis.publisher_distribution)
        report.append("")

        # Combined scores
        report.append("COMBINED Similarity Scores:")
        report.append("-" * 28)
        self._add_distribution_stats(report, analysis.combined_distribution)
        report.append("")

        # Recommended thresholds
        conservative_thresholds = analysis.get_recommended_thresholds(5)
        moderate_thresholds = analysis.get_recommended_thresholds(10)

        report.append("RECOMMENDED THRESHOLDS:")
        report.append("-" * 23)
        report.append("Conservative (5th percentile):")
        for field, threshold in conservative_thresholds.items():
            report.append(f"  {field}: {threshold:.1f}")
        report.append("")
        report.append("Moderate (10th percentile):")
        for field, threshold in moderate_thresholds.items():
            report.append(f"  {field}: {threshold:.1f}")

        return "\n".join(report)

    def _add_distribution_stats(self, report: list[str], dist: ScoreDistribution) -> None:
        """Add distribution statistics to report"""
        if not dist.scores:
            report.append("  No scores available")
            return

        report.append(f"  Count: {len(dist.scores):,}")
        report.append(f"  Mean: {dist.mean_score:.1f}")
        report.append(f"  Median: {dist.median_score:.1f}")
        report.append(f"  Std Dev: {dist.std_dev:.1f}")
        report.append(f"  Range: {dist.min_score:.1f} - {dist.max_score:.1f}")
        report.append(f"  Percentiles:")
        report.append(f"    5th: {dist.percentile_5:.1f}")
        report.append(f"    25th: {dist.percentile_25:.1f}")
        report.append(f"    75th: {dist.percentile_75:.1f}")
        report.append(f"    95th: {dist.percentile_95:.1f}")

    def compare_algorithms(
        self,
        ground_truth_pairs: list[GroundTruthPair],
        fuzzy_matcher: DataMatcher | None,
        word_matcher: DataMatcher,
    ) -> dict[str, GroundTruthAnalysis]:
        """Compare similarity score distributions between algorithms

        Args:
            ground_truth_pairs: List of verified ground truth pairs
            fuzzy_matcher: Fuzzy string matching algorithm
            word_matcher: Word-based matching algorithm

        Returns:
            Dictionary with analysis results for each algorithm
        """
        self.logger.info("Comparing algorithm performance on ground truth pairs")

        # Analyze with fuzzy string matching
        original_matcher = self.matcher
        if fuzzy_matcher:
            self.matcher = fuzzy_matcher
            fuzzy_analysis = self.analyze_ground_truth_scores(ground_truth_pairs)
        else:
            # Create empty analysis when no fuzzy matcher is provided
            empty_dist = ScoreDistribution("empty", [])
            fuzzy_analysis = GroundTruthAnalysis(
                total_pairs=0,
                registration_pairs=0,
                renewal_pairs=0,
                title_distribution=empty_dist,
                author_distribution=empty_dist,
                publisher_distribution=empty_dist,
                combined_distribution=empty_dist,
                pairs_by_match_type={},
            )

        # Analyze with word-based matching
        self.matcher = word_matcher
        word_analysis = self.analyze_ground_truth_scores(ground_truth_pairs)

        # Restore original matcher
        self.matcher = original_matcher

        return {"fuzzy_string": fuzzy_analysis, "word_based": word_analysis}

    def export_score_data(self, analysis: GroundTruthAnalysis, output_file: str) -> None:
        """Export detailed score data for further analysis

        Args:
            analysis: Ground truth analysis results
            output_file: Path to output CSV file
        """
        # Standard library imports
        from csv import writer

        with open(output_file, "w", newline="") as f:
            csv_writer = writer(f)

            # Header
            csv_writer.writerow(
                cast(
                    list[str],
                    [
                        "pair_index",
                        "match_type",
                        "lccn",
                        "marc_title",
                        "copyright_title",
                        "title_score",
                        "marc_author",
                        "copyright_author",
                        "author_score",
                        "marc_publisher",
                        "copyright_publisher",
                        "publisher_score",
                        "combined_score",
                    ],
                )
            )

            # Data rows
            for i, pair in enumerate(
                analysis.pairs_by_match_type.get("registration", [])
                + analysis.pairs_by_match_type.get("renewal", [])
            ):

                # Calculate scores for this pair
                match_result = self._calculate_text_similarity(
                    pair.marc_record, pair.copyright_record
                )

                if match_result:
                    scores = match_result["similarity_scores"]
                    # Type check - scores should be a dict
                    if isinstance(scores, dict):
                        csv_writer.writerow(
                            cast(
                                list[str | int | float],
                                [
                                    i,
                                    pair.match_type,
                                    pair.lccn,
                                    pair.marc_record.title or "",
                                    pair.copyright_record.title or "",
                                    scores.get("title", 0.0),
                                    pair.marc_record.author or "",
                                    pair.copyright_record.author or "",
                                    scores.get("author", 0.0),
                                    pair.marc_record.publisher or "",
                                    pair.copyright_record.publisher or "",
                                    scores.get("publisher", 0.0),
                                    scores.get("combined", 0.0),
                                ],
                            )
                        )

        self.logger.info(f"Score data exported to {output_file}")
