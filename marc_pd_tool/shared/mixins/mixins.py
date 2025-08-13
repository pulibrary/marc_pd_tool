# marc_pd_tool/shared/mixins/mixins.py

"""Common mixins for reducing code duplication across classes

When to use mixins vs utility functions:
- Mixins: For shared behavior across multiple classes that need instance methods
  and/or access to instance state (e.g., ConfigurableMixin, YearFilterableMixin)
- Utils: For standalone functions that transform data without needing instance
  state (e.g., text normalization, LCCN processing)

Current mixins:
- ConfigurableMixin: Used by 3+ classes for standardized config access
- YearFilterableMixin: Used by 2+ loader classes for year-based filtering
"""

# Standard library imports
from logging import getLogger
from typing import TYPE_CHECKING
from typing import TypeVar
from typing import cast

T = TypeVar("T")

if TYPE_CHECKING:
    from marc_pd_tool.core.domain.publication import Publication

# Local imports
from marc_pd_tool.core.types.json import JSONDict
from marc_pd_tool.core.types.json import JSONType
from marc_pd_tool.infrastructure.config import ConfigLoader
from marc_pd_tool.infrastructure.config import get_config

logger = getLogger(__name__)


class ConfigurableMixin:
    """Mixin for classes that need configuration access

    Provides standardized config initialization pattern used across:
    - DataMatcher
    - SimilarityCalculator
    - DataIndexer
    - GenericTitleDetector
    """

    def _init_config(self, config: ConfigLoader | None = None) -> ConfigLoader:
        """Initialize configuration, using default if not provided

        Args:
            config: Optional ConfigLoader instance

        Returns:
            ConfigLoader instance (provided or default)
        """
        if config is None:
            config = get_config()
        return config

    def _get_config_value(self, config_dict: JSONDict, path: str, default: T) -> T:
        """Safely navigate nested config dictionary using dot notation

        Args:
            config_dict: Configuration dictionary
            path: Dot-separated path (e.g., "matching.word_based.min_chars")
            default: Default value if path not found or not a dict

        Returns:
            Config value or default (type preserved)

        Example:
            value = self._get_config_value(config, "matching.adaptive_weighting.title_weight", 0.5)
        """
        keys = path.split(".")
        current: JSONType = config_dict

        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return default

        # Try to preserve type if possible
        if isinstance(current, type(default)) or (current is None and default is None):
            return cast(T, current)
        else:
            # Attempt type conversion for common cases
            try:
                if isinstance(default, (int, float)) and isinstance(current, (int, float, str)):
                    return cast(T, type(default)(current))
                elif isinstance(default, str) and not isinstance(current, (dict, list)):
                    return cast(T, str(current))
                elif isinstance(default, bool) and isinstance(current, (bool, int, str)):
                    if isinstance(current, str):
                        return cast(T, current.lower() in ("true", "1", "yes", "on"))
                    return cast(T, bool(current))
            except (ValueError, TypeError):
                pass

            return default


class YearFilterableMixin:
    """Mixin for loaders that need year-based filtering

    Provides standardized year filtering logic used in:
    - CopyrightDataLoader
    - RenewalDataLoader
    """

    def _filter_by_year(
        self,
        publications: list["Publication"],
        min_year: int | None = None,
        max_year: int | None = None,
    ) -> list["Publication"]:
        """Filter publications by year range

        Args:
            publications: List of publications to filter
            min_year: Minimum year (inclusive), None for no minimum
            max_year: Maximum year (inclusive), None for no maximum

        Returns:
            Filtered list of publications
        """
        if min_year is None and max_year is None:
            return publications

        filtered = []
        for pub in publications:
            if pub.year is not None:
                if min_year is not None and pub.year < min_year:
                    continue
                if max_year is not None and pub.year > max_year:
                    continue
            # Include publications with year in range or no year
            filtered.append(pub)

        return filtered

    def _log_year_filtering(
        self, min_year: int | None, max_year: int | None, source_name: str
    ) -> None:
        """Log year filtering information

        Args:
            min_year: Minimum year filter
            max_year: Maximum year filter
            source_name: Name of data source (e.g., "copyright", "renewal")
        """
        if min_year is not None or max_year is not None:
            logger.info(
                f"Loading {source_name} data for years "
                f"{min_year or 'earliest'}-{max_year or 'latest'}..."
            )
        else:
            logger.info(f"Loading all {source_name} data...")
