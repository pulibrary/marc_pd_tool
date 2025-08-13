# marc_pd_tool/application/services/_indexing_service.py

"""Indexing service for managing publication data indexes.

This service orchestrates the creation and management of various indexes
(title, author, publisher, year, LCCN) for fast publication lookup.
"""

# Standard library imports
from logging import getLogger

# Local imports
from marc_pd_tool.application.processing.indexer import DataIndexer
from marc_pd_tool.core.domain.publication import Publication
from marc_pd_tool.infrastructure import CacheManager
from marc_pd_tool.infrastructure.config import ConfigLoader
from marc_pd_tool.infrastructure.persistence import CopyrightDataLoader
from marc_pd_tool.infrastructure.persistence import RenewalDataLoader

logger = getLogger(__name__)


class IndexingService:
    """Application service for managing publication indexing operations.

    This service coordinates the loading, indexing, and caching of
    copyright and renewal data for efficient matching operations.
    """

    __slots__ = (
        "_config",
        "_cache_manager",
        "_copyright_loader",
        "_renewal_loader",
        "_indexer",
        "_indexed_publications",
    )

    def __init__(
        self, config: ConfigLoader | None = None, cache_manager: CacheManager | None = None
    ) -> None:
        """Initialize the indexing service.

        Args:
            config: Configuration loader, uses default if None
            cache_manager: Cache manager for persistence
        """
        self._config = config or ConfigLoader()
        self._cache_manager = cache_manager
        self._copyright_loader: CopyrightDataLoader | None = None
        self._renewal_loader: RenewalDataLoader | None = None
        self._indexer: DataIndexer | None = None
        self._indexed_publications: list[Publication] = []

    def load_and_index_data(
        self,
        copyright_data_path: str,
        renewal_data_path: str,
        min_year: int | None = None,
        max_year: int | None = None,
        force_refresh: bool = False,
    ) -> DataIndexer:
        """Load and index copyright and renewal data.

        Args:
            copyright_data_path: Path to copyright XML data
            renewal_data_path: Path to renewal TSV data
            min_year: Optional minimum year filter
            max_year: Optional maximum year filter
            force_refresh: Force cache refresh if True

        Returns:
            Configured and populated data indexer
        """
        # Check cache first if available
        if self._cache_manager and not force_refresh:
            cached_indexer = self._cache_manager.load_cached_index(
                min_year=min_year, max_year=max_year
            )
            if cached_indexer:
                logger.info("Loaded indexed data from cache")
                self._indexer = cached_indexer
                self._indexed_publications = cached_indexer.publications
                return cached_indexer

        # Load copyright data
        logger.info("Loading copyright registration data...")
        self._copyright_loader = CopyrightDataLoader(config=self._config)
        copyright_pubs = self._copyright_loader.load_copyright_data(
            copyright_data_path, min_year=min_year, max_year=max_year
        )

        # Load renewal data
        logger.info("Loading renewal data...")
        self._renewal_loader = RenewalDataLoader(config=self._config)
        renewal_pubs = self._renewal_loader.load_renewal_data(
            renewal_data_path, min_year=min_year, max_year=max_year
        )

        # Combine all publications
        all_publications = copyright_pubs + renewal_pubs
        self._indexed_publications = all_publications

        # Create and populate indexer
        logger.info(f"Indexing {len(all_publications):,} publications...")
        self._indexer = DataIndexer(config_loader=self._config)

        for pub in all_publications:
            self._indexer.add_publication(pub)

        # Cache if manager available
        if self._cache_manager:
            self._cache_manager.save_cached_index(
                self._indexer, min_year=min_year, max_year=max_year
            )
            logger.info("Saved indexed data to cache")

        return self._indexer

    def get_candidates_for_publication(
        self, publication: Publication, year_tolerance: int = 1
    ) -> list[Publication]:
        """Get candidate matches for a publication.

        Args:
            publication: Publication to find candidates for
            year_tolerance: Maximum year difference allowed

        Returns:
            List of candidate publications that could match
        """
        if not self._indexer:
            logger.warning("No indexer available - returning empty candidates")
            return []

        # Use the indexer's candidate finding logic
        candidate_ids = self._indexer.find_candidates_wordbased(
            publication, year_tolerance=year_tolerance
        )

        # Convert IDs to publications
        candidates = [self._indexer.publications[pub_id] for pub_id in candidate_ids]

        return candidates

    @property
    def indexer(self) -> DataIndexer | None:
        """Get the current data indexer."""
        return self._indexer

    @property
    def publication_count(self) -> int:
        """Get the number of indexed publications."""
        return len(self._indexed_publications) if self._indexed_publications else 0

    @property
    def publications(self) -> list[Publication]:
        """Get all indexed publications."""
        return self._indexed_publications
