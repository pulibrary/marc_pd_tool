"""Configuration loading and management for MARC copyright analysis tool"""

# Standard library imports
from json import load as json_load
from os.path import exists
from typing import Any
from typing import Dict
from typing import Optional


class ConfigLoader:
    """Handles loading and merging of JSON configuration files"""

    def __init__(self, config_path: Optional[str] = None):
        """Initialize configuration loader

        Args:
            config_path: Path to JSON configuration file, None for defaults only
        """
        self.config_path = config_path
        self._config = self._load_config()

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration values"""
        return {
            "scoring_weights": {
                "normal_with_publisher": {"title": 0.6, "author": 0.25, "publisher": 0.15},
                "generic_with_publisher": {"title": 0.3, "author": 0.45, "publisher": 0.25},
                "normal_no_publisher": {"title": 0.7, "author": 0.3},
                "generic_no_publisher": {"title": 0.4, "author": 0.6},
            },
            "default_thresholds": {
                "title": 80,
                "author": 70,
                "publisher": 60,
                "early_exit_title": 95,
                "early_exit_author": 90,
                "year_tolerance": 2,
            },
            "generic_title_detector": {"frequency_threshold": 10},
            "word_lists": {
                "stopwords": [
                    "a",
                    "an",
                    "and",
                    "are",
                    "as",
                    "at",
                    "be",
                    "by",
                    "for",
                    "from",
                    "has",
                    "he",
                    "in",
                    "is",
                    "it",
                    "its",
                    "of",
                    "on",
                    "or",
                    "that",
                    "the",
                    "to",
                    "was",
                    "were",
                    "will",
                    "with",
                ],
                "publisher_stopwords": [
                    "inc",
                    "corp",
                    "corporation",
                    "company",
                    "co",
                    "ltd",
                    "limited",
                    "publishers",
                    "publisher",
                    "publishing",
                    "publications",
                    "press",
                    "books",
                    "book",
                    "house",
                    "group",
                    "media",
                    "entertainment",
                ],
                "edition_stopwords": [
                    "edition",
                    "ed",
                    "printing",
                    "print",
                    "impression",
                    "issue",
                    "vol",
                    "volume",
                ],
                "ordinal_terms": [
                    "1st",
                    "first",
                    "2nd",
                    "second",
                    "3rd",
                    "third",
                    "4th",
                    "fourth",
                    "5th",
                    "fifth",
                    "revised",
                    "rev",
                    "new",
                    "updated",
                    "enlarged",
                    "expanded",
                    "abridged",
                    "complete",
                ],
            },
        }

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file with fallback to defaults

        Returns:
            Complete configuration dictionary
        """
        defaults = self._get_default_config()

        if not self.config_path or not exists(self.config_path):
            return defaults

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                user_config = json_load(f)

            # Deep merge user config with defaults
            return self._deep_merge(defaults, user_config)

        except (FileNotFoundError, PermissionError, OSError) as e:
            print(f"Warning: Could not read config file {self.config_path}: {e}")
            return defaults
        except Exception as e:
            print(f"Warning: Invalid JSON in config file {self.config_path}: {e}")
            return defaults

    def _deep_merge(self, base: Dict[str, Any], update: Dict[str, Any]) -> Dict[str, Any]:
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
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value

        return result

    def get_scoring_weights(self, scenario: str) -> Dict[str, float]:
        """Get scoring weights for a specific scenario

        Args:
            scenario: One of 'normal_with_publisher', 'generic_with_publisher',
                     'normal_no_publisher', 'generic_no_publisher'

        Returns:
            Dictionary with title, author, and optionally publisher weights
        """
        return self._config["scoring_weights"].get(scenario, {})

    def get_threshold(self, threshold_name: str) -> int:
        """Get a specific threshold value

        Args:
            threshold_name: Name of threshold (title, author, publisher, etc.)

        Returns:
            Threshold value
        """
        return self._config["default_thresholds"].get(threshold_name, 80)

    def get_generic_detector_config(self) -> Dict[str, Any]:
        """Get generic title detector configuration

        Returns:
            Configuration dictionary for GenericTitleDetector
        """
        return self._config["generic_title_detector"]

    def get_word_list(self, list_name: str) -> list:
        """Get a specific word list

        Args:
            list_name: Name of word list (stopwords, publisher_stopwords, edition_stopwords)

        Returns:
            List of words
        """
        return self._config["word_lists"].get(list_name, [])

    def get_stopwords(self) -> set:
        """Get stopwords as a set for efficient lookup

        Returns:
            Set of stopwords
        """
        return set(self.get_word_list("stopwords"))

    def get_publisher_stopwords(self) -> set:
        """Get publisher stopwords as a set for efficient lookup

        Returns:
            Set of publisher stopwords
        """
        return set(self.get_word_list("publisher_stopwords"))

    def get_edition_stopwords(self) -> set:
        """Get edition stopwords as a set for efficient lookup

        Returns:
            Set of edition stopwords
        """
        return set(self.get_word_list("edition_stopwords"))

    def get_ordinal_terms(self) -> set:
        """Get ordinal terms as a set for efficient lookup

        Returns:
            Set of ordinal terms
        """
        return set(self.get_word_list("ordinal_terms"))

    def reload(self) -> None:
        """Reload configuration from file"""
        self._config = self._load_config()


# Global default instance for backward compatibility
_default_config_loader = ConfigLoader()


def get_config(config_path: Optional[str] = None) -> ConfigLoader:
    """Get configuration loader instance

    Args:
        config_path: Path to configuration file, None for default

    Returns:
        ConfigLoader instance
    """
    if config_path:
        return ConfigLoader(config_path)
    return _default_config_loader


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """Load configuration from JSON file with fallback to defaults

    Args:
        config_path: Path to JSON configuration file

    Returns:
        Complete configuration dictionary
    """
    loader = get_config(config_path)
    return loader._config
