# marc_pd_tool/application/processing/matching/_core_matcher.py

"""Core matching engine that orchestrates all matching components"""

# Standard library imports
from logging import getLogger

# Local imports
from marc_pd_tool.application.processing.derived_work_detector import (
    DerivedWorkDetector,
)
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
        self.derived_work_detector = DerivedWorkDetector()

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
        # Find best match (including LCCN matches with proper scoring)
        best_match = None
        best_score = -1.0  # Start at -1 to track any valid match

        # Track LCCN matches for each publication
        lccn_match_map: dict[str, bool] = {}

        # Check for LCCN matches upfront to build the map
        if marc_pub.normalized_lccn:
            for copyright_pub in copyright_pubs:
                if (
                    copyright_pub.normalized_lccn
                    and marc_pub.normalized_lccn == copyright_pub.normalized_lccn
                ):
                    lccn_match_map[copyright_pub.source_id or ""] = True
                    logger.debug(
                        f"LCCN match found for {marc_pub.normalized_lccn} "
                        f"with source {copyright_pub.source_id}"
                    )

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
            # Try both author fields and use the best match
            author_score = 0.0

            # Score 1: Compare main_author (100/110) fields
            if marc_pub.main_author or copyright_pub.main_author:
                main_author_score = self.similarity_calculator.calculate_similarity(
                    marc_pub.main_author, copyright_pub.main_author, "author", language
                )
            else:
                main_author_score = 0.0

            # Score 2: Compare author (245c) fields
            if marc_pub.author or copyright_pub.author:
                regular_author_score = self.similarity_calculator.calculate_similarity(
                    marc_pub.author, copyright_pub.author, "author", language
                )
            else:
                regular_author_score = 0.0

            # Score 3: Cross-compare main_author with author
            if marc_pub.main_author and copyright_pub.author:
                cross_score_1 = self.similarity_calculator.calculate_similarity(
                    marc_pub.main_author, copyright_pub.author, "author", language
                )
            else:
                cross_score_1 = 0.0

            # Score 4: Cross-compare author with main_author
            if marc_pub.author and copyright_pub.main_author:
                cross_score_2 = self.similarity_calculator.calculate_similarity(
                    marc_pub.author, copyright_pub.main_author, "author", language
                )
            else:
                cross_score_2 = 0.0

            # Use the best score from all comparisons
            author_score = max(
                main_author_score, regular_author_score, cross_score_1, cross_score_2
            )

            # Only check author threshold if we have some author data
            if author_score > 0:
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

            # Check if this is an LCCN match
            has_lccn_match = lccn_match_map.get(copyright_pub.source_id or "", False)

            # Phase 5: Check for derived works
            marc_derived, copyright_derived = self.derived_work_detector.detect(
                marc_pub.title, copyright_pub.title, language
            )

            # Combine scores (with LCCN boost if applicable)
            combined_score = self.score_combiner.combine_scores(
                title_score,
                author_score,
                publisher_score,
                has_generic_title=has_generic,
                use_config_weights=True,
                has_lccn_match=has_lccn_match,
                marc_derived=marc_derived,
                copyright_derived=copyright_derived,
            )

            # Check for early exit (perfect match)
            # If no author data exists, ignore author early exit threshold
            # Check both author fields for presence of data
            has_author_data = (
                marc_pub.author
                or marc_pub.main_author
                or copyright_pub.author
                or copyright_pub.main_author
            )
            author_check = (
                early_exit_author is None  # No author threshold set
                or not has_author_data  # No author data in any field
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
                    is_lccn_match=has_lccn_match,
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
                    is_lccn_match=has_lccn_match,
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
        # Find best match (including LCCN matches with proper scoring)
        best_match = None
        best_score = -1.0  # Start at -1 to accept even 0-score matches

        # Track LCCN matches for each publication
        lccn_match_map: dict[str, bool] = {}

        # Check for LCCN matches upfront to build the map
        if marc_pub.normalized_lccn:
            for copyright_pub in copyright_pubs:
                if (
                    copyright_pub.normalized_lccn
                    and marc_pub.normalized_lccn == copyright_pub.normalized_lccn
                ):
                    lccn_match_map[copyright_pub.source_id or ""] = True
                    logger.debug(
                        f"LCCN match found for {marc_pub.normalized_lccn} "
                        f"with source {copyright_pub.source_id}"
                    )

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

            # Try all author field combinations and use the best score
            author_scores = []

            # Compare main_author fields
            if marc_pub.main_author or copyright_pub.main_author:
                author_scores.append(
                    self.similarity_calculator.calculate_similarity(
                        marc_pub.main_author, copyright_pub.main_author, "author", language
                    )
                )

            # Compare author (245c) fields
            if marc_pub.author or copyright_pub.author:
                author_scores.append(
                    self.similarity_calculator.calculate_similarity(
                        marc_pub.author, copyright_pub.author, "author", language
                    )
                )

            # Cross-compare main_author with author
            if marc_pub.main_author and copyright_pub.author:
                author_scores.append(
                    self.similarity_calculator.calculate_similarity(
                        marc_pub.main_author, copyright_pub.author, "author", language
                    )
                )

            # Cross-compare author with main_author
            if marc_pub.author and copyright_pub.main_author:
                author_scores.append(
                    self.similarity_calculator.calculate_similarity(
                        marc_pub.author, copyright_pub.main_author, "author", language
                    )
                )

            author_score = max(author_scores) if author_scores else 0.0

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

            # Check if this is an LCCN match
            has_lccn_match = lccn_match_map.get(copyright_pub.source_id or "", False)

            # Phase 5: Check for derived works
            marc_derived, copyright_derived = self.derived_work_detector.detect(
                marc_pub.title, copyright_pub.title, language
            )

            # Combine scores (with LCCN boost if applicable)
            combined_score = self.score_combiner.combine_scores(
                title_score,
                author_score,
                publisher_score,
                has_generic_title=has_generic,
                use_config_weights=True,
                has_lccn_match=has_lccn_match,
                marc_derived=marc_derived,
                copyright_derived=copyright_derived,
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
                    is_lccn_match=has_lccn_match,
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
