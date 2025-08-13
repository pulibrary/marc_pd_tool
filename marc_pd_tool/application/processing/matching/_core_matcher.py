# marc_pd_tool/application/processing/matching/_core_matcher.py

"""Core matching engine that orchestrates all matching components"""

# Standard library imports
from logging import getLogger

# Local imports
from marc_pd_tool.application.processing.matching._lccn_matcher import LCCNMatcher
from marc_pd_tool.application.processing.matching._match_builder import (
    MatchResultBuilder,
)
from marc_pd_tool.application.processing.matching._score_combiner import ScoreCombiner
from marc_pd_tool.application.processing.similarity_calculator import (
    SimilarityCalculator,
)
from marc_pd_tool.application.processing.text_processing import GenericTitleDetector
from marc_pd_tool.core.domain.publication import Publication
from marc_pd_tool.core.types.results import MatchResultDict
from marc_pd_tool.infrastructure.config import ConfigLoader
from marc_pd_tool.shared.mixins.mixins import ConfigurableMixin

logger = getLogger(__name__)


class CoreMatcher(ConfigurableMixin):
    """Core matching engine for comparing MARC records against copyright/renewal data"""

    def __init__(
        self,
        config: ConfigLoader | None = None,
        similarity_calculator: SimilarityCalculator | None = None,
        generic_detector: GenericTitleDetector | None = None,
    ):
        """Initialize core matcher with components

        Args:
            config: Configuration loader
            similarity_calculator: Similarity calculator
            generic_detector: Generic title detector
        """
        self.config = self._init_config(config)

        # Initialize components
        self.lccn_matcher = LCCNMatcher()
        self.score_combiner = ScoreCombiner(self.config)
        self.match_builder = MatchResultBuilder()

        # Use provided or create new similarity calculator
        self.similarity_calculator = similarity_calculator or SimilarityCalculator(self.config)
        self.generic_detector = generic_detector

    def find_best_match(
        self,
        marc_pub: Publication,
        copyright_pubs: list[Publication],
        title_threshold: int,
        author_threshold: int,
        publisher_threshold: int | None = None,
        year_tolerance: int = 1,
        early_exit_title: int = 95,
        early_exit_author: int = 90,
        early_exit_publisher: int | None = None,
    ) -> MatchResultDict | None:
        """Find best matching copyright/renewal record

        Args:
            marc_pub: MARC publication to match
            copyright_pubs: List of copyright/renewal publications
            title_threshold: Minimum title similarity score
            author_threshold: Minimum author similarity score
            publisher_threshold: Minimum publisher similarity score
            year_tolerance: Maximum year difference allowed
            early_exit_title: Title score for early termination
            early_exit_author: Author score for early termination
            early_exit_publisher: Publisher score for early termination

        Returns:
            Best match result or None if no match meets thresholds
        """
        # Check for LCCN match first (in normal mode, don't calculate scores)
        lccn_match = self.lccn_matcher.find_lccn_match(
            marc_pub, copyright_pubs, calculate_scores=False
        )
        if lccn_match:
            return lccn_match

        # Find best similarity-based match
        best_match = None
        best_score = -1.0  # Start at -1 to track any valid match

        for copyright_pub in copyright_pubs:
            # Skip if year difference too large
            if not self._check_year_tolerance(marc_pub, copyright_pub, year_tolerance):
                continue

            # Calculate similarity scores
            language = marc_pub.language_code or "eng"
            title_score = self.similarity_calculator.calculate_similarity(
                marc_pub.title, copyright_pub.title, "title", language
            )

            # Skip if title doesn't meet threshold
            if title_score < title_threshold:
                continue

            # Calculate author score and check threshold
            author_score = 0.0
            # Only check author threshold if at least one has author data
            if marc_pub.author or copyright_pub.author:
                author_score = self.similarity_calculator.calculate_similarity(
                    marc_pub.author, copyright_pub.author, "author", language
                )

                # Skip if author doesn't meet threshold
                if author_score < author_threshold:
                    continue

            # Calculate publisher score if threshold provided
            publisher_score = 0.0
            if publisher_threshold is not None and marc_pub.publisher and copyright_pub.publisher:
                publisher_score = self.similarity_calculator.calculate_similarity(
                    marc_pub.publisher, copyright_pub.publisher, "publisher", language
                )

                # Skip if publisher doesn't meet threshold
                if publisher_score < publisher_threshold:
                    continue

            # Check for generic title
            has_generic = False
            if self.generic_detector:
                marc_generic = self.generic_detector.is_generic(marc_pub.title)
                copyright_generic = self.generic_detector.is_generic(copyright_pub.title)
                has_generic = marc_generic or copyright_generic

            # Combine scores
            combined_score = self.score_combiner.combine_scores(
                title_score,
                author_score,
                publisher_score,
                has_generic_title=has_generic,
                use_config_weights=True,
            )

            # Check for early exit (perfect match)
            # If no author data exists, ignore author early exit threshold
            author_check = (
                early_exit_author is None  # No author threshold set
                or not (marc_pub.author or copyright_pub.author)  # No author data
                or author_score >= early_exit_author  # Author score meets threshold
            )

            # If no publisher data exists, ignore publisher early exit threshold
            publisher_check = (
                early_exit_publisher is None  # No publisher threshold set
                or not (marc_pub.publisher and copyright_pub.publisher)  # No publisher data
                or publisher_score >= early_exit_publisher  # Publisher score meets threshold
            )

            if title_score >= early_exit_title and author_check and publisher_check:
                return self.match_builder.create_match_result(
                    marc_pub,
                    copyright_pub,
                    title_score,
                    author_score,
                    publisher_score,
                    combined_score,
                    self.generic_detector,
                    is_lccn_match=False,
                )

            # Track best match
            if combined_score > best_score:
                best_score = combined_score
                best_match = self.match_builder.create_match_result(
                    marc_pub,
                    copyright_pub,
                    title_score,
                    author_score,
                    publisher_score,
                    combined_score,
                    self.generic_detector,
                    is_lccn_match=False,
                )

        return best_match

    def find_best_match_ignore_thresholds(
        self,
        marc_pub: Publication,
        copyright_pubs: list[Publication],
        year_tolerance: int = 1,
        minimum_combined_score: int | None = None,
    ) -> MatchResultDict | None:
        """Find best match ignoring individual thresholds

        Used for score_everything mode to find best match regardless of thresholds.

        Args:
            marc_pub: MARC publication to match
            copyright_pubs: List of copyright/renewal publications
            year_tolerance: Maximum year difference allowed
            minimum_combined_score: Minimum combined score required

        Returns:
            Best match result or None if no match found
        """
        # Check for LCCN match first (in score_everything mode, calculate scores)
        lccn_match = self.lccn_matcher.find_lccn_match(
            marc_pub, copyright_pubs, calculate_scores=True
        )
        if lccn_match:
            return lccn_match

        # Find best match without thresholds
        best_match = None
        best_score = -1.0  # Start at -1 to accept even 0-score matches

        for copyright_pub in copyright_pubs:
            # Skip if year difference too large (unless no year)
            if marc_pub.year is not None and not self._check_year_tolerance(
                marc_pub, copyright_pub, year_tolerance
            ):
                continue

            # Calculate all scores
            language = marc_pub.language_code or "eng"
            title_score = self.similarity_calculator.calculate_similarity(
                marc_pub.title, copyright_pub.title, "title", language
            )

            author_score = self.similarity_calculator.calculate_similarity(
                marc_pub.author, copyright_pub.author, "author", language
            )

            publisher_score = 0.0
            if marc_pub.publisher and copyright_pub.publisher:
                publisher_score = self.similarity_calculator.calculate_similarity(
                    marc_pub.publisher, copyright_pub.publisher, "publisher", language
                )

            # Check for generic title
            has_generic = False
            if self.generic_detector:
                marc_generic = self.generic_detector.is_generic(marc_pub.title)
                copyright_generic = self.generic_detector.is_generic(copyright_pub.title)
                has_generic = marc_generic or copyright_generic

            # Combine scores
            combined_score = self.score_combiner.combine_scores(
                title_score,
                author_score,
                publisher_score,
                has_generic_title=has_generic,
                use_config_weights=True,
            )

            # Apply minimum combined score filter if specified
            if minimum_combined_score is not None and combined_score < minimum_combined_score:
                continue

            # Track best match
            if combined_score > best_score:
                best_score = combined_score
                best_match = self.match_builder.create_match_result(
                    marc_pub,
                    copyright_pub,
                    title_score,
                    author_score,
                    publisher_score,
                    combined_score,
                    self.generic_detector,
                    is_lccn_match=False,
                )

        return best_match

    def _check_year_tolerance(
        self, marc_pub: Publication, copyright_pub: Publication, year_tolerance: int
    ) -> bool:
        """Check if publications are within year tolerance

        Args:
            marc_pub: MARC publication
            copyright_pub: Copyright/renewal publication
            year_tolerance: Maximum year difference

        Returns:
            True if within tolerance or year data missing
        """
        if marc_pub.year is None or copyright_pub.year is None:
            return True  # Can't filter by year if missing

        return abs(marc_pub.year - copyright_pub.year) <= year_tolerance
