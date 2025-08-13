# marc_pd_tool/application/processing/matching/_score_combiner.py

"""Score combination and weighting logic for matching"""

# Standard library imports
from logging import getLogger

# Local imports
from marc_pd_tool.core.types.json import JSONDict
from marc_pd_tool.infrastructure.config import ConfigLoader

logger = getLogger(__name__)


class ScoreCombiner:
    """Handles score combination and adaptive weighting"""

    def __init__(self, config: ConfigLoader):
        """Initialize with configuration

        Args:
            config: Configuration loader
        """
        self.config = config

        # Load weight configurations
        config_dict = config.config
        self.default_title_weight = self._get_weight(config_dict, "title_weight", 0.5)
        self.default_author_weight = self._get_weight(config_dict, "author_weight", 0.3)
        self.default_publisher_weight = self._get_weight(config_dict, "publisher_weight", 0.2)
        self.generic_title_penalty = self._get_weight(config_dict, "generic_title_penalty", 0.8)

    def _get_weight(self, config_dict: JSONDict, key: str, default: float) -> float:
        """Get weight value from config with default

        Args:
            config_dict: Configuration dictionary
            key: Weight key to look up
            default: Default value if not found

        Returns:
            Weight value as float
        """
        weight = config_dict.get("matching", {}).get("adaptive_weighting", {}).get(key, default)
        # Pydantic ensures these are valid types, just convert to float
        return float(weight)

    def combine_scores(
        self,
        title_score: float,
        author_score: float,
        publisher_score: float = 0.0,
        has_generic_title: bool = False,
        use_config_weights: bool = True,
    ) -> float:
        """Combine individual scores into final similarity score

        Args:
            title_score: Title similarity score (0-100)
            author_score: Author similarity score (0-100)
            publisher_score: Publisher similarity score (0-100)
            has_generic_title: Whether title is generic
            use_config_weights: Whether to use config weights or determine dynamically

        Returns:
            Combined similarity score (0-100)
        """
        if use_config_weights:
            # Use weights from configuration
            if has_generic_title:
                scenario = (
                    "generic_with_publisher" if publisher_score > 0 else "generic_no_publisher"
                )
            else:
                scenario = "normal_with_publisher" if publisher_score > 0 else "normal_no_publisher"

            weights = self.config.get_scoring_weights(scenario)

            if weights:
                title_weight = weights.get("title", self.default_title_weight)
                author_weight = weights.get("author", self.default_author_weight)
                publisher_weight = weights.get("publisher", self.default_publisher_weight)
            else:
                # Fallback to defaults
                title_weight = self.default_title_weight
                author_weight = self.default_author_weight
                publisher_weight = self.default_publisher_weight if publisher_score > 0 else 0
        else:
            # Dynamic weight calculation based on scores
            title_weight, author_weight, publisher_weight = self._calculate_dynamic_weights(
                title_score, author_score, publisher_score, has_generic_title
            )

        # Apply generic title penalty if needed
        if has_generic_title:
            title_weight *= self.generic_title_penalty

        # Normalize weights
        total_weight = title_weight + author_weight + publisher_weight
        if total_weight > 0:
            title_weight /= total_weight
            author_weight /= total_weight
            publisher_weight /= total_weight

        # Calculate combined score
        combined = (
            title_score * title_weight
            + author_score * author_weight
            + publisher_score * publisher_weight
        )

        return round(combined, 2)

    def _calculate_dynamic_weights(
        self,
        title_score: float,
        author_score: float,
        publisher_score: float,
        has_generic_title: bool,
    ) -> tuple[float, float, float]:
        """Calculate dynamic weights based on score values

        Args:
            title_score: Title similarity score
            author_score: Author similarity score
            publisher_score: Publisher similarity score
            has_generic_title: Whether title is generic

        Returns:
            Tuple of (title_weight, author_weight, publisher_weight)
        """
        # High confidence in one field can boost its weight
        if title_score >= 90 and not has_generic_title:
            title_weight = 0.6
            author_weight = 0.25
            publisher_weight = 0.15
        elif author_score >= 90:
            title_weight = 0.3 if has_generic_title else 0.4
            author_weight = 0.5
            publisher_weight = 0.2 if publisher_score > 0 else 0.1
        elif publisher_score >= 80:
            title_weight = 0.25 if has_generic_title else 0.35
            author_weight = 0.35
            publisher_weight = 0.3
        else:
            # Default weights
            title_weight = self.default_title_weight
            author_weight = self.default_author_weight
            publisher_weight = self.default_publisher_weight if publisher_score > 0 else 0

        return title_weight, author_weight, publisher_weight
