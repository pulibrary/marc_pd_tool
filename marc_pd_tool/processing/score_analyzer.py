# marc_pd_tool/processing/score_analyzer.py

"""Analyze similarity scores for ground truth pairs"""

# Standard library imports
from collections import defaultdict
from logging import getLogger

# Local imports
from marc_pd_tool.data.ground_truth import GroundTruthAnalysis
from marc_pd_tool.data.ground_truth import GroundTruthPair
from marc_pd_tool.data.ground_truth import ScoreDistribution
from marc_pd_tool.data.publication import Publication
from marc_pd_tool.processing.matching_engine import DataMatcher
from marc_pd_tool.processing.text_processing import GenericTitleDetector
from marc_pd_tool.utils.types import MatchResultDict

logger = getLogger(__name__)


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

        return "\n".join(report)

    def _add_distribution_stats(self, report: list[str], dist: ScoreDistribution) -> None:
        """Add distribution statistics to report"""
        if not dist.scores:
            report.append("  No scores available")
            return

        report.append(f"  Count: {len(dist.scores)}")
        report.append(f"  Mean: {dist.mean_score:.1f}")
        report.append(f"  Median: {dist.median_score:.1f}")
        report.append(f"  Std Dev: {dist.std_dev:.1f}")
        report.append(f"  Min: {dist.min_score:.1f}")
        report.append(f"  Max: {dist.max_score:.1f}")
        report.append(f"  5th percentile: {dist.percentile_5:.1f}")
        report.append(f"  25th percentile: {dist.percentile_25:.1f}")
        report.append(f"  75th percentile: {dist.percentile_75:.1f}")
        report.append(f"  95th percentile: {dist.percentile_95:.1f}")
