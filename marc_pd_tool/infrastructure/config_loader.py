# marc_pd_tool/infrastructure/config_loader.py

"""Configuration loading and management for MARC copyright analysis tool"""

# Standard library imports
from json import load as json_load
from logging import getLogger
from os.path import exists
from typing import cast

# Local imports
from marc_pd_tool.utils.types import JSONDict
from marc_pd_tool.utils.types import JSONType
from marc_pd_tool.utils.types import MatchingConfig
from marc_pd_tool.utils.types import WordBasedConfig
from marc_pd_tool.utils.types import Wordlists

logger = getLogger(__name__)


class ConfigLoader:
    """Handles loading and merging of JSON configuration files"""

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
        # Standard library imports
        from os import getcwd
        from os.path import join

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
                "batch_size": 200,
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
                result[key] = self._deep_merge(cast(JSONDict, result[key]), value)
            else:
                result[key] = value

        return result

    def get_scoring_weights(self, scenario: str) -> dict[str, float]:
        """Get scoring weights for a specific scenario

        Args:
            scenario: One of 'normal_with_publisher', 'generic_with_publisher',
                     'normal_no_publisher', 'generic_no_publisher'

        Returns:
            Dictionary with title, author, and optionally publisher weights
        """
        weights = self._config.get("scoring_weights", {})
        if isinstance(weights, dict):
            scenario_weights = weights.get(scenario, {})
            if isinstance(scenario_weights, dict):
                return {k: v for k, v in scenario_weights.items() if isinstance(v, (int, float))}
        return {}

    def get_threshold(self, threshold_name: str) -> int:
        """Get a specific threshold value

        Args:
            threshold_name: Name of threshold (title, author, publisher, etc.)

        Returns:
            Threshold value
        """
        thresholds = self._config.get("default_thresholds", {})
        if isinstance(thresholds, dict):
            value = thresholds.get(threshold_name, 80)
            if isinstance(value, (int, float)):
                return int(value)
        return 80

    def get_generic_detector_config(self) -> dict[str, int]:
        """Get generic title detector configuration

        Returns:
            Configuration dictionary for GenericTitleDetector
        """
        config = self._config.get("generic_title_detector", {"frequency_threshold": 10})
        if isinstance(config, dict):
            return {k: int(v) for k, v in config.items() if isinstance(v, (int, float))}
        return {"frequency_threshold": 10}

    def get_stopwords_set(self) -> set[str]:
        """Get stopwords as a set for efficient lookup

        Returns:
            Set of stopwords
        """
        return set(self.get_stopwords("general"))

    def get_publisher_stopwords(self) -> set[str]:
        """Get publisher stopwords as a set for efficient lookup

        Returns:
            Set of publisher stopwords
        """
        return set(self.get_stopwords("publisher"))

    def get_edition_stopwords(self) -> set[str]:
        """Get edition stopwords as a set for efficient lookup

        Returns:
            Set of edition stopwords
        """
        return set(self.get_stopwords("edition"))

    def get_ordinal_terms(self) -> set[str]:
        """Get ordinal terms as a set for efficient lookup

        Returns:
            Set of ordinal terms
        """
        return set(self.get_patterns("ordinals"))

    def get_config(self) -> JSONDict:
        """Get the complete configuration dictionary

        Returns:
            Complete configuration dictionary
        """
        return self._config

    def get_matching_config(self) -> MatchingConfig:
        """Get matching engine configuration

        Returns:
            Configuration dictionary for matching engines
        """
        matching = self._config.get("matching", {})
        if isinstance(matching, dict):
            word_based_raw = matching.get("word_based", {})
            if isinstance(word_based_raw, dict):
                # Ensure all required fields are present
                word_based: WordBasedConfig = {
                    "default_language": str(word_based_raw.get("default_language", "eng")),
                    "enable_stemming": bool(word_based_raw.get("enable_stemming", True)),
                    "enable_abbreviation_expansion": bool(
                        word_based_raw.get("enable_abbreviation_expansion", True)
                    ),
                }
                return MatchingConfig(word_based=word_based)
        # Default config
        default_word_based: WordBasedConfig = {
            "default_language": "eng",
            "enable_stemming": True,
            "enable_abbreviation_expansion": True,
        }
        return MatchingConfig(word_based=default_word_based)

    def get_processing_config(self) -> JSONDict:
        """Get processing configuration

        Returns:
            Dictionary with batch_size, max_workers, score_everything_mode, brute_force_missing_year
        """
        processing = self._config.get("processing", {})
        if isinstance(processing, dict):
            return dict(processing)
        return {}

    def get_filtering_config(self) -> JSONDict:
        """Get filtering configuration

        Returns:
            Dictionary with min_year, max_year, us_only
        """
        filtering = self._config.get("filtering", {})
        if isinstance(filtering, dict):
            return dict(filtering)
        return {}

    def get_output_config(self) -> JSONDict:
        """Get output configuration

        Returns:
            Dictionary with single_file setting
        """
        output = self._config.get("output", {})
        if isinstance(output, dict):
            return dict(output)
        return {}

    def get_caching_config(self) -> JSONDict:
        """Get caching configuration

        Returns:
            Dictionary with cache_dir, force_refresh, no_cache
        """
        caching = self._config.get("caching", {})
        if isinstance(caching, dict):
            return dict(caching)
        return {}

    def get_logging_config(self) -> JSONDict:
        """Get logging configuration

        Returns:
            Dictionary with debug, log_file
        """
        logging = self._config.get("logging", {})
        if isinstance(logging, dict):
            return dict(logging)
        return {}

    def reload(self) -> None:
        """Reload configuration from file"""
        self._config = self._load_config()
        self._wordlists = self._load_wordlists()

    def _resolve_wordlists_path(self) -> str | None:
        """Find wordlists.json file in same directory as config

        Returns:
            Path to wordlists.json if found, None otherwise
        """
        # Check in same directory as config
        if self.config_path:
            # Standard library imports
            import os

            config_dir = os.path.dirname(self.config_path)
            wordlists_path = os.path.join(config_dir, "wordlists.json")
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

    def get_wordlists(self) -> Wordlists | None:
        """Get the wordlists dictionary

        Returns:
            Wordlists dictionary or None
        """
        return self._wordlists

    def get_abbreviations(self) -> dict[str, str]:
        """Get abbreviations dictionary

        Returns:
            Abbreviations mapping
        """
        if self._wordlists and "abbreviations" in self._wordlists:
            abbrevs = self._wordlists["abbreviations"].get("bibliographic", {})
            # Ensure we return a proper dict[str, str]
            return {k: v for k, v in abbrevs.items() if isinstance(k, str) and isinstance(v, str)}
        return {}

    def get_stopwords(self, category: str = "general") -> list[str]:
        """Get stopwords list by category

        Args:
            category: Stopword category (general, publisher, edition, title, author)

        Returns:
            List of stopwords
        """
        if self._wordlists and "stopwords" in self._wordlists:
            words = self._wordlists["stopwords"].get(category, [])
            # Ensure we return a proper list[str]
            return [w for w in words if isinstance(w, str)]
        # Return empty list if no wordlists loaded
        return []

    def get_patterns(self, pattern_type: str) -> list[str]:
        """Get pattern list by type

        Args:
            pattern_type: Pattern type (generic_titles, ordinals, etc.)

        Returns:
            List of patterns
        """
        if self._wordlists and "patterns" in self._wordlists:
            patterns = self._wordlists["patterns"].get(pattern_type, [])
            # Ensure we return a proper list[str]
            return [p for p in patterns if isinstance(p, str)]
        return []

    def get_author_stopwords(self) -> set[str]:
        """Get author stopwords as a set for efficient lookup

        Returns:
            Set of author stopwords
        """
        if self._wordlists and "stopwords" in self._wordlists:
            return set(self._wordlists["stopwords"].get("author", []))
        return set()

    def get_unicode_corrections(self) -> dict[str, str]:
        """Get Unicode encoding corruption corrections mapping

        Returns:
            Dictionary mapping corrupted characters to correct ones
        """
        if self._wordlists and "text_fixes" in self._wordlists:
            result = self._wordlists["text_fixes"].get("unicode_corrections", {})
            return dict(result)
        return {}

    def get_combined_stopwords(self, *categories: str) -> set[str]:
        """Get combined stopwords from multiple categories

        Args:
            *categories: Variable number of category names (e.g., "general", "title", "author")

        Returns:
            Set of combined stopwords from all specified categories
        """
        result = set()
        for category in categories:
            stopwords = self.get_stopwords(category)
            result.update(stopwords)
        return result

    def get_all_stopwords(self) -> set[str]:
        """Get all stopwords from all categories

        Returns:
            Set of all stopwords across all categories
        """
        if self._wordlists and "stopwords" in self._wordlists:
            all_stopwords = set()
            for category_stopwords in self._wordlists["stopwords"].values():
                if isinstance(category_stopwords, list):
                    all_stopwords.update(category_stopwords)
            return all_stopwords
        return set()

    def get_title_processing_config(self) -> JSONDict:
        """Get all configuration needed for title processing

        Returns:
            Dictionary with stopwords, abbreviations, and generic patterns
        """
        return {
            "stopwords": cast(list[JSONType], list(self.get_stopwords("title"))),
            "abbreviations": cast(JSONDict, self.get_abbreviations()),
            "generic_patterns": cast(list[JSONType], self.get_patterns("generic_titles")),
        }

    def get_author_processing_config(self) -> JSONDict:
        """Get all configuration needed for author processing

        Returns:
            Dictionary with stopwords, titles, and other author-specific config
        """
        return {
            "stopwords": cast(list[JSONType], list(self.get_author_stopwords())),
            "titles": cast(list[JSONType], self.get_patterns("author_titles")),
            "abbreviations": cast(JSONDict, self.get_abbreviations()),
        }

    def get_publisher_suffixes(self) -> list[str]:
        """Get publisher suffix patterns for normalization

        Returns:
            List of publisher suffix patterns
        """
        return self.get_patterns("publisher_suffixes")

    def get_publisher_suffix_regex(self) -> str:
        """Get compiled regex pattern for publisher suffixes

        Returns:
            Regex pattern string for matching publisher suffixes
        """
        suffixes = self.get_publisher_suffixes()
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
