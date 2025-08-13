# marc_pd_tool/application/services/_analysis_service.py

"""Analysis service for orchestrating copyright status analysis.

This service coordinates the complete analysis workflow from loading
MARC records through matching and copyright status determination.
"""

# Standard library imports
from logging import getLogger

# Local imports
from marc_pd_tool.application.models.analysis_results import AnalysisResults
from marc_pd_tool.application.services._indexing_service import IndexingService
from marc_pd_tool.application.services._matching_service import MatchingService
from marc_pd_tool.core.domain.publication import Publication
from marc_pd_tool.infrastructure import CacheManager
from marc_pd_tool.infrastructure.config import ConfigLoader
from marc_pd_tool.infrastructure.persistence import MarcLoader

logger = getLogger(__name__)


class AnalysisService:
    """Application service for orchestrating copyright analysis operations.

    This service manages the complete workflow of analyzing MARC records
    for copyright status, coordinating between loading, indexing, matching,
    and status determination.
    """

    __slots__ = (
        "_config",
        "_cache_manager",
        "_indexing_service",
        "_matching_service",
        "_marc_loader",
    )

    def __init__(
        self, config: ConfigLoader | None = None, cache_manager: CacheManager | None = None
    ) -> None:
        """Initialize the analysis service.

        Args:
            config: Configuration loader, uses default if None
            cache_manager: Cache manager for persistence
        """
        self._config = config or ConfigLoader()
        self._cache_manager = cache_manager
        self._indexing_service = IndexingService(config=self._config, cache_manager=cache_manager)
        self._matching_service = MatchingService(config=self._config)
        self._marc_loader: MarcLoader | None = None

    def analyze_marc_file(
        self,
        marc_file_path: str,
        copyright_data_path: str,
        renewal_data_path: str,
        min_year: int | None = None,
        max_year: int | None = None,
        us_only: bool = False,
        force_refresh: bool = False,
        title_threshold: int = 40,
        author_threshold: int = 30,
        publisher_threshold: int | None = None,
        year_tolerance: int = 1,
        early_exit_title: int = 95,
        early_exit_author: int = 90,
        early_exit_publisher: int | None = None,
    ) -> AnalysisResults:
        """Analyze a MARC file for copyright status.

        Args:
            marc_file_path: Path to MARC XML file
            copyright_data_path: Path to copyright data
            renewal_data_path: Path to renewal data
            min_year: Optional minimum year filter
            max_year: Optional maximum year filter
            us_only: Filter to US publications only
            force_refresh: Force cache refresh
            title_threshold: Minimum title similarity score
            author_threshold: Minimum author similarity score
            publisher_threshold: Optional publisher similarity threshold
            year_tolerance: Maximum year difference
            early_exit_title: Title score for immediate acceptance
            early_exit_author: Author score for immediate acceptance
            early_exit_publisher: Optional publisher score for immediate acceptance

        Returns:
            Analysis results with matches and statistics
        """
        # Load and index copyright/renewal data
        logger.info("Loading and indexing copyright/renewal data...")
        indexer = self._indexing_service.load_and_index_data(
            copyright_data_path=copyright_data_path,
            renewal_data_path=renewal_data_path,
            min_year=min_year,
            max_year=max_year,
            force_refresh=force_refresh,
        )

        # Load MARC records
        logger.info(f"Loading MARC records from {marc_file_path}...")
        self._marc_loader = MarcLoader(config=self._config)
        marc_publications = self._marc_loader.load_marc_file(marc_file_path, us_only=us_only)

        # Process each MARC record
        results = AnalysisResults()

        for marc_pub in marc_publications:
            # Skip if no year and not forcing
            if not marc_pub.year:
                results.skipped_no_year += 1
                continue

            # Get candidates
            candidates = self._indexing_service.get_candidates_for_publication(
                marc_pub, year_tolerance=year_tolerance
            )

            if not candidates:
                results.no_matches.append(marc_pub)
                continue

            # Find best match
            match_result = self._matching_service.find_matches(
                marc_publication=marc_pub,
                candidate_publications=candidates,
                title_threshold=title_threshold,
                author_threshold=author_threshold,
                publisher_threshold=publisher_threshold,
                year_tolerance=year_tolerance,
                early_exit_title=early_exit_title,
                early_exit_author=early_exit_author,
                early_exit_publisher=early_exit_publisher,
            )

            if match_result:
                # Determine copyright status
                marc_pub.determine_copyright_status(match_result)
                results.matches.append((marc_pub, match_result))
            else:
                results.no_matches.append(marc_pub)

        # Calculate statistics
        results.total_processed = len(marc_publications)
        results.total_matched = len(results.matches)
        results.match_rate = (
            results.total_matched / results.total_processed if results.total_processed > 0 else 0.0
        )

        return results

    def analyze_single_publication(
        self,
        publication: Publication,
        year_tolerance: int = 1,
        title_threshold: int = 40,
        author_threshold: int = 30,
        publisher_threshold: int | None = None,
    ) -> tuple[Publication, dict] | None:
        """Analyze a single publication for copyright status.

        Args:
            publication: Publication to analyze
            year_tolerance: Maximum year difference
            title_threshold: Minimum title similarity
            author_threshold: Minimum author similarity
            publisher_threshold: Optional publisher similarity

        Returns:
            Tuple of (publication, match_result) or None if no match
        """
        if not self._indexing_service.indexer:
            logger.error("No indexer available - run analyze_marc_file first")
            return None

        # Get candidates
        candidates = self._indexing_service.get_candidates_for_publication(
            publication, year_tolerance=year_tolerance
        )

        if not candidates:
            return None

        # Find match
        match_result = self._matching_service.find_matches(
            marc_publication=publication,
            candidate_publications=candidates,
            title_threshold=title_threshold,
            author_threshold=author_threshold,
            publisher_threshold=publisher_threshold,
            year_tolerance=year_tolerance,
        )

        if match_result:
            publication.determine_copyright_status(match_result)
            return (publication, match_result)

        return None

    @property
    def config(self) -> ConfigLoader:
        """Get the configuration loader."""
        return self._config

    @property
    def indexing_service(self) -> IndexingService:
        """Get the indexing service."""
        return self._indexing_service

    @property
    def matching_service(self) -> MatchingService:
        """Get the matching service."""
        return self._matching_service
