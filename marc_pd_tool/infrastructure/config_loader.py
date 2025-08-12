# marc_pd_tool/infrastructure/config_loader.py

"""Configuration loading and management for MARC copyright analysis tool"""

# Standard library imports
from functools import cached_property
from json import load as json_load
from logging import getLogger
from os import getcwd
from os.path import dirname
from os.path import exists
from os.path import join

# Local imports
from marc_pd_tool.utils.types import JSONDict
from marc_pd_tool.utils.types import MatchingConfig
from marc_pd_tool.utils.types import WordBasedConfig
from marc_pd_tool.utils.types import Wordlists

logger = getLogger(__name__)


class ConfigLoader:
    """Handles loading and merging of JSON configuration files

    This class provides a clean property-based API for accessing configuration
    values. All expensive computations are automatically cached using @cached_property.
    """

    def __init__(self, config_path: str | None = None):
        """Initialize configuration loader

        Args:
            config_path: Path to JSON configuration file, None for auto-detection
        """
        self.config_path = self._resolve_config_path(config_path)
        self.wordlists_path = self._resolve_wordlists_path()
        self._config: JSONDict = self._load_config()
        self._wordlists: Wordlists | None = self._load_wordlists()

    def _resolve_config_path(self, config_path: str | None) -> str | None:
        """Resolve configuration file path with auto-detection

        Args:
            config_path: Explicit path or None for auto-detection

        Returns:
            Resolved config path or None if not found
        """
        # If explicit path provided, use it
        if config_path:
            return config_path

        # Auto-detect config.json in current working directory
        auto_config_path = join(getcwd(), "config.json")
        if exists(auto_config_path):
            return auto_config_path

        # No config file found
        return None

    def _get_default_config(self) -> JSONDict:
        """Get default configuration values"""
        return {
            "scoring_weights": {
                "normal_with_publisher": {"title": 0.6, "author": 0.25, "publisher": 0.15},
                "generic_with_publisher": {"title": 0.3, "author": 0.45, "publisher": 0.25},
                "normal_no_publisher": {"title": 0.7, "author": 0.3},
                "generic_no_publisher": {"title": 0.4, "author": 0.6},
            },
            "default_thresholds": {
                "title": 40,
                "author": 30,
                "publisher": 60,
                "early_exit_title": 95,
                "early_exit_author": 90,
                "year_tolerance": 1,
                "minimum_combined_score": 40,
            },
            "matching": {
                "word_based": {
                    "default_language": "eng",
                    "enable_stemming": True,
                    "enable_abbreviation_expansion": True,
                }
            },
            "generic_title_detector": {
                "frequency_threshold": 10,
                "disable_generic_detection": False,
            },
            "processing": {
                "batch_size": 100,
                "max_workers": None,
                "score_everything_mode": False,
                "brute_force_missing_year": False,
            },
            "filtering": {"min_year": None, "max_year": None, "us_only": False},
            "output": {"single_file": False},
            "caching": {"cache_dir": ".marcpd_cache", "force_refresh": False, "no_cache": False},
            "logging": {"debug": False, "log_file": None},
        }

    def _load_config(self) -> JSONDict:
        """Load configuration from file with fallback to defaults

        Returns:
            Complete configuration dictionary
        """
        defaults = self._get_default_config()

        if not self.config_path or not exists(self.config_path):
            logger.debug("Using built-in default configuration")
            return defaults

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                user_config = json_load(f)

            logger.debug(f"Loaded configuration from: {self.config_path}")
            # Deep merge user config with defaults
            return self._deep_merge(defaults, user_config)

        except (FileNotFoundError, PermissionError, OSError) as e:
            logger.warning(f"Could not read config file {self.config_path}: {e}")
            return defaults
        except Exception as e:
            logger.warning(f"Invalid JSON in config file {self.config_path}: {e}")
            return defaults

    def _deep_merge(self, base: JSONDict, update: JSONDict) -> JSONDict:
        """Deep merge two dictionaries, with update values taking precedence

        Args:
            base: Base dictionary (defaults)
            update: Update dictionary (user config)

        Returns:
            Merged dictionary
        """
        result = base.copy()

        for key, value in update.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)  # type: ignore[arg-type]
            else:
                result[key] = value

        return result

    def _resolve_wordlists_path(self) -> str | None:
        """Find wordlists.json file in same directory as config

        Returns:
            Path to wordlists.json if found, None otherwise
        """
        # Check in same directory as config
        if self.config_path:
            config_dir = dirname(self.config_path)
            wordlists_path = join(config_dir, "wordlists.json")
            if exists(wordlists_path):
                return wordlists_path

        # Check in current directory
        if exists("wordlists.json"):
            return "wordlists.json"

        return None

    def _load_wordlists(self) -> Wordlists | None:
        """Load wordlists from JSON file

        Returns:
            Wordlists dictionary or None
        """
        if self.wordlists_path and exists(self.wordlists_path):
            try:
                with open(self.wordlists_path, "r") as f:
                    wordlists = json_load(f)
                logger.info(f"Loaded wordlists from {self.wordlists_path}")
                # Cast the loaded JSON to our Wordlists type
                return Wordlists(
                    abbreviations=wordlists.get("abbreviations", {"bibliographic": {}}),
                    stopwords=wordlists.get("stopwords", {}),
                    patterns=wordlists.get("patterns", {}),
                    text_fixes=wordlists.get("text_fixes", {"unicode_corrections": {}}),
                )
            except Exception as e:
                logger.warning(f"Failed to load wordlists from {self.wordlists_path}: {e}")
        else:
            logger.debug("No wordlists.json found, using embedded defaults")

        return None

    # ============= Simple Properties (no caching needed) =============

    @property
    def config(self) -> JSONDict:
        """Complete configuration dictionary"""
        return self._config

    @property
    def wordlists(self) -> Wordlists | None:
        """Wordlists dictionary if loaded"""
        return self._wordlists

    @property
    def processing_config(self) -> JSONDict:
        """Processing configuration section"""
        result = self._config.get("processing", {})
        return result if isinstance(result, dict) else {}

    @property
    def filtering_config(self) -> JSONDict:
        """Filtering configuration section"""
        result = self._config.get("filtering", {})
        return result if isinstance(result, dict) else {}

    @property
    def output_config(self) -> JSONDict:
        """Output configuration section"""
        result = self._config.get("output", {})
        return result if isinstance(result, dict) else {}

    @property
    def caching_config(self) -> JSONDict:
        """Caching configuration section"""
        result = self._config.get("caching", {})
        return result if isinstance(result, dict) else {}

    @property
    def logging_config(self) -> JSONDict:
        """Logging configuration section"""
        result = self._config.get("logging", {})
        return result if isinstance(result, dict) else {}

    # ============= Cached Properties (expensive computations) =============

    @cached_property
    def stopwords_set(self) -> set[str]:
        """General stopwords as a set for efficient lookup"""
        return set(self._get_stopwords("general"))

    @cached_property
    def publisher_stopwords(self) -> set[str]:
        """Publisher-specific stopwords as a set"""
        return set(self._get_stopwords("publisher"))

    @cached_property
    def edition_stopwords(self) -> set[str]:
        """Edition-specific stopwords as a set"""
        return set(self._get_stopwords("edition"))

    @cached_property
    def author_stopwords(self) -> set[str]:
        """Author-specific stopwords as a set"""
        return set(self._get_stopwords("author"))

    @cached_property
    def title_stopwords(self) -> set[str]:
        """Title-specific stopwords as a set"""
        return set(self._get_stopwords("title"))

    @cached_property
    def all_stopwords(self) -> set[str]:
        """All stopwords from all categories combined"""
        if self._wordlists and "stopwords" in self._wordlists:
            all_words = set()
            for category_stopwords in self._wordlists["stopwords"].values():
                if isinstance(category_stopwords, list):
                    all_words.update(category_stopwords)
            return all_words
        return set()

    @cached_property
    def ordinal_terms(self) -> set[str]:
        """Ordinal terms (first, second, 1st, 2nd, etc.) as a set"""
        return set(self._get_patterns("ordinals"))

    @cached_property
    def generic_title_patterns(self) -> set[str]:
        """Generic title patterns as a set"""
        return set(self._get_patterns("generic_titles"))

    @cached_property
    def matching_config(self) -> MatchingConfig:
        """Matching engine configuration"""
        matching = self._config.get("matching", {})
        word_based_raw = matching.get("word_based", {})  # type: ignore[union-attr]
        # Ensure all required fields are present
        word_based: WordBasedConfig = {
            "default_language": str(word_based_raw.get("default_language", "eng")),  # type: ignore[union-attr]
            "enable_stemming": bool(word_based_raw.get("enable_stemming", True)),  # type: ignore[union-attr]
            "enable_abbreviation_expansion": bool(
                word_based_raw.get("enable_abbreviation_expansion", True)  # type: ignore[union-attr]
            ),
        }
        return MatchingConfig(word_based=word_based)

    @cached_property
    def generic_detector_config(self) -> dict[str, int]:
        """Generic title detector configuration"""
        config = self._config.get("generic_title_detector", {"frequency_threshold": 10})
        return {k: int(v) for k, v in config.items() if isinstance(v, (int, float))}  # type: ignore[union-attr]

    @cached_property
    def abbreviations(self) -> dict[str, str]:
        """Bibliographic abbreviations mapping"""
        if self._wordlists and "abbreviations" in self._wordlists:
            abbrevs = self._wordlists["abbreviations"].get("bibliographic", {})
            return {k: str(v) for k, v in abbrevs.items() if isinstance(k, str)}
        return {}

    @cached_property
    def unicode_corrections(self) -> dict[str, str]:
        """Unicode encoding corruption corrections"""
        if self._wordlists and "text_fixes" in self._wordlists:
            result = self._wordlists["text_fixes"].get("unicode_corrections", {})
            return dict(result)
        return {}

    @cached_property
    def publisher_suffixes(self) -> list[str]:
        """Publisher suffix patterns for normalization"""
        return self._get_patterns("publisher_suffixes")

    @cached_property
    def publisher_suffix_regex(self) -> str:
        """Compiled regex pattern for publisher suffixes"""
        suffixes = self.publisher_suffixes
        if suffixes:
            # Handle plurals with ? in the pattern
            pattern_parts = []
            for suffix in suffixes:
                if suffix in ["publisher", "book"]:
                    pattern_parts.append(f"{suffix}s?")
                else:
                    pattern_parts.append(suffix)
            return r"\b(" + "|".join(pattern_parts) + r")\b"
        return ""

    @cached_property
    def title_processing_config(self) -> JSONDict:
        """All configuration needed for title processing"""
        return {
            "stopwords": list(self.title_stopwords),
            "abbreviations": (
                self.abbreviations
            ),  # dict[str, str] is already compatible with JSONType
            "generic_patterns": list(self.generic_title_patterns),
        }

    @cached_property
    def author_processing_config(self) -> JSONDict:
        """All configuration needed for author processing"""
        return {
            "stopwords": list(self.author_stopwords),
            "titles": self._get_patterns("author_titles"),
            "abbreviations": (
                self.abbreviations
            ),  # dict[str, str] is already compatible with JSONType
        }

    # ============= Public Methods (need parameters) =============

    def get_scoring_weights(self, scenario: str) -> dict[str, float]:
        """Get scoring weights for a specific scenario

        Args:
            scenario: One of 'normal_with_publisher', 'generic_with_publisher',
                     'normal_no_publisher', 'generic_no_publisher'

        Returns:
            Dictionary with title, author, and optionally publisher weights
        """
        weights = self._config.get("scoring_weights", {})
        scenario_weights = weights.get(scenario, {})  # type: ignore[union-attr]
        return {k: float(v) for k, v in scenario_weights.items() if isinstance(v, (int, float))}  # type: ignore[union-attr]

    def get_threshold(self, threshold_name: str) -> int:
        """Get a specific threshold value

        Args:
            threshold_name: Name of threshold (title, author, publisher, etc.)

        Returns:
            Threshold value
        """
        thresholds = self._config.get("default_thresholds", {})
        value = thresholds.get(threshold_name, 80)  # type: ignore[union-attr]
        if isinstance(value, (int, float)):
            return int(value)
        return 80

    def get_combined_stopwords(self, *categories: str) -> set[str]:
        """Get combined stopwords from multiple categories

        Args:
            *categories: Variable number of category names

        Returns:
            Set of combined stopwords from all specified categories
        """
        result = set()
        for category in categories:
            stopwords = self._get_stopwords(category)
            result.update(stopwords)
        return result

    # ============= Private Helper Methods =============

    def _get_stopwords(self, category: str = "general") -> list[str]:
        """INTERNAL: Get stopwords list by category

        Args:
            category: Stopword category

        Returns:
            List of stopwords for the category
        """
        if self._wordlists and "stopwords" in self._wordlists:
            words = self._wordlists["stopwords"].get(category, [])
            # Ensure we return a proper list[str]
            return [str(w) for w in words]
        # Return empty list if no wordlists loaded
        return []

    def _get_patterns(self, pattern_type: str) -> list[str]:
        """INTERNAL: Get pattern list by type

        Args:
            pattern_type: Pattern type

        Returns:
            List of patterns
        """
        if self._wordlists and "patterns" in self._wordlists:
            patterns = self._wordlists["patterns"].get(pattern_type, [])
            # Ensure we return a proper list[str]
            return [str(p) for p in patterns]
        return []


# Global default instance - uses auto-detection
_default_config_loader = ConfigLoader(None)


def get_config(config_path: str | None = None) -> ConfigLoader:
    """Get configuration loader instance

    Args:
        config_path: Path to configuration file, None for default

    Returns:
        ConfigLoader instance
    """
    if config_path:
        return ConfigLoader(config_path)
    return _default_config_loader


def load_config(config_path: str | None = None) -> JSONDict:
    """Load configuration from JSON file with fallback to defaults

    Args:
        config_path: Path to JSON configuration file

    Returns:
        Complete configuration dictionary
    """
    loader = get_config(config_path)
    return loader._config
