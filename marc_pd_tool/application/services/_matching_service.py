# marc_pd_tool/application/services/_matching_service.py

"""Matching service for orchestrating MARC record matching operations.

This service coordinates the matching workflow between MARC records and
copyright/renewal data, managing the interaction between the indexer,
matcher, and result builder components.
"""

# Standard library imports
from logging import getLogger

# Local imports
from marc_pd_tool.application.processing.matching._core_matcher import CoreMatcher
from marc_pd_tool.application.processing.similarity_calculator import (
    SimilarityCalculator,
)
from marc_pd_tool.application.processing.text_processing import GenericTitleDetector
from marc_pd_tool.core.domain.publication import Publication
from marc_pd_tool.core.types.results import MatchResultDict
from marc_pd_tool.infrastructure.config import ConfigLoader

logger = getLogger(__name__)


class MatchingService:
    """Application service for coordinating matching operations.

    This service orchestrates the matching workflow, managing the interaction
    between various components to find the best matches for MARC records.
    """

    __slots__ = ("_matcher", "_config", "_generic_detector")

    def __init__(
        self,
        config: ConfigLoader | None = None,
        similarity_calculator: SimilarityCalculator | None = None,
        generic_detector: GenericTitleDetector | None = None,
    ) -> None:
        """Initialize the matching service.

        Args:
            config: Configuration loader, uses default if None
            similarity_calculator: Custom similarity calculator
            generic_detector: Generic title detector
        """
        self._config = config or ConfigLoader()
        self._matcher = CoreMatcher(
            config=self._config, similarity_calculator=similarity_calculator
        )
        self._generic_detector = generic_detector or GenericTitleDetector(config=self._config)

    def find_matches(
        self,
        marc_publication: Publication,
        candidate_publications: list[Publication],
        title_threshold: int = 40,
        author_threshold: int = 30,
        publisher_threshold: int | None = None,
        year_tolerance: int = 1,
        early_exit_title: int = 95,
        early_exit_author: int = 90,
        early_exit_publisher: int | None = None,
    ) -> MatchResultDict | None:
        """Find the best match for a MARC publication.

        Args:
            marc_publication: The MARC record to match
            candidate_publications: List of potential matches from copyright/renewal data
            title_threshold: Minimum similarity score for title matching
            author_threshold: Minimum similarity score for author matching
            publisher_threshold: Optional minimum score for publisher matching
            year_tolerance: Maximum year difference allowed
            early_exit_title: Title score for immediate match acceptance
            early_exit_author: Author score for immediate match acceptance
            early_exit_publisher: Optional publisher score for immediate acceptance

        Returns:
            Best matching result or None if no match found
        """
        if not candidate_publications:
            logger.debug("No candidate publications provided for matching")
            return None

        # Configure the matcher with current settings
        self._matcher.generic_detector = self._generic_detector

        # Delegate to the core matcher
        return self._matcher.find_best_match(
            marc_pub=marc_publication,
            copyright_pubs=candidate_publications,
            title_threshold=title_threshold,
            author_threshold=author_threshold,
            publisher_threshold=publisher_threshold,
            year_tolerance=year_tolerance,
            early_exit_title=early_exit_title,
            early_exit_author=early_exit_author,
            early_exit_publisher=early_exit_publisher,
        )

    def find_all_matches(
        self,
        marc_publication: Publication,
        candidate_publications: list[Publication],
        year_tolerance: int = 1,
    ) -> list[MatchResultDict]:
        """Find all potential matches for threshold analysis.

        Args:
            marc_publication: The MARC record to match
            candidate_publications: List of potential matches
            year_tolerance: Maximum year difference allowed

        Returns:
            List of all scored matches, sorted by combined score
        """
        if not candidate_publications:
            return []

        # Use the matcher's score_everything mode
        result = self._matcher.find_best_match_ignore_thresholds(
            marc_pub=marc_publication,
            copyright_pubs=candidate_publications,
            year_tolerance=year_tolerance,
        )

        # Return single result as list for compatibility
        return [result] if result else []

    @property
    def config(self) -> ConfigLoader:
        """Get the configuration loader."""
        return self._config

    @property
    def matcher(self) -> CoreMatcher:
        """Get the underlying matcher for advanced operations."""
        return self._matcher
