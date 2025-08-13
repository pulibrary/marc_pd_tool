# marc_pd_tool/infrastructure/config/_loader.py

"""Main configuration loader using Pydantic models"""

# Standard library imports
from functools import cached_property
from logging import getLogger
from pathlib import Path

# Third party imports
from pydantic import BaseModel

# Local imports
from marc_pd_tool.core.types.json import JSONDict
from marc_pd_tool.infrastructure.config._models import AppConfig
from marc_pd_tool.infrastructure.config._wordlists import WordlistsConfig

logger = getLogger(__name__)


class ConfigLoader:
    """Configuration loader that provides both config and wordlists

    This replaces the old ConfigLoader with a Pydantic-based implementation.
    No backward compatibility - direct replacement.
    """

    def __init__(self, config_path: str | None = None):
        """Initialize configuration loader

        Args:
            config_path: Path to JSON configuration file, None for auto-detection
        """
        # Load main config
        self.config_path = config_path
        self._app_config = AppConfig.load(config_path)

        # Load wordlists
        self._wordlists = WordlistsConfig.load(self._find_wordlists_path())

    def _find_wordlists_path(self) -> Path | None:
        """Find wordlists.json file"""
        # Check in same directory as config
        if self.config_path:
            config_path = Path(self.config_path)
            wordlists_path = config_path.parent / "wordlists.json"
            if wordlists_path.exists():
                return wordlists_path

        # Check in current directory
        wordlists_path = Path("wordlists.json")
        if wordlists_path.exists():
            return wordlists_path

        return None

    # Direct access to Pydantic config objects
    @property
    def config(self) -> JSONDict:
        """Full config as dict for any legacy code that needs it"""
        return self._app_config.model_dump()

    @property
    def processing(self) -> BaseModel:
        """Processing configuration"""
        return self._app_config.processing

    @property
    def filtering(self) -> BaseModel:
        """Filtering configuration"""
        return self._app_config.filtering

    @property
    def output(self) -> BaseModel:
        """Output configuration"""
        return self._app_config.output

    @property
    def caching(self) -> BaseModel:
        """Caching configuration"""
        return self._app_config.caching

    @property
    def logging(self) -> BaseModel:
        """Logging configuration"""
        return self._app_config.logging

    @property
    def matching(self) -> BaseModel:
        """Matching configuration"""
        return self._app_config.matching

    @property
    def generic_detector(self) -> BaseModel:
        """Generic detector configuration"""
        return self._app_config.generic_title_detector

    @property
    def wordlists(self) -> WordlistsConfig | None:
        """Wordlists if loaded"""
        return self._wordlists

    # Threshold access
    def get_threshold(self, name: str) -> int:
        """Get threshold value by name"""
        return self._app_config.get_threshold(name)

    def get_scoring_weights(self, scenario: str) -> dict[str, float]:
        """Get scoring weights for a scenario"""
        weights_config = self._app_config.scoring_weights.model_dump()
        return weights_config.get(scenario, {})

    # Cached computed properties for commonly used values
    @cached_property
    def stopwords_set(self) -> set[str]:
        """General stopwords as a set"""
        if self._wordlists:
            return set(self._wordlists.get_stopwords("general"))
        return set()

    @cached_property
    def publisher_stopwords(self) -> set[str]:
        """Publisher stopwords as a set"""
        if self._wordlists:
            return set(self._wordlists.get_stopwords("publisher"))
        return set()

    @cached_property
    def author_stopwords(self) -> set[str]:
        """Author stopwords as a set"""
        if self._wordlists:
            return set(self._wordlists.get_stopwords("author"))
        return set()

    @cached_property
    def title_stopwords(self) -> set[str]:
        """Title stopwords as a set"""
        if self._wordlists:
            return set(self._wordlists.get_stopwords("title"))
        return set()

    @cached_property
    def edition_stopwords(self) -> set[str]:
        """Edition stopwords as a set"""
        if self._wordlists:
            return set(self._wordlists.get_stopwords("edition"))
        return set()

    @cached_property
    def all_stopwords(self) -> set[str]:
        """All stopwords combined"""
        if self._wordlists:
            return self._wordlists.get_all_stopwords()
        return set()

    @cached_property
    def generic_title_patterns(self) -> set[str]:
        """Generic title patterns"""
        if self._wordlists:
            return set(self._wordlists.get_patterns("generic_titles"))
        return set()

    @cached_property
    def ordinal_terms(self) -> set[str]:
        """Ordinal terms"""
        if self._wordlists:
            return set(self._wordlists.get_patterns("ordinals"))
        return set()

    @cached_property
    def abbreviations(self) -> dict[str, str]:
        """Bibliographic abbreviations"""
        if self._wordlists:
            return self._wordlists.get_abbreviations()
        return {}

    @cached_property
    def unicode_corrections(self) -> dict[str, str]:
        """Unicode corrections"""
        if self._wordlists:
            return self._wordlists.get_unicode_corrections()
        return {}

    @cached_property
    def publisher_suffixes(self) -> list[str]:
        """Publisher suffixes"""
        if self._wordlists:
            return self._wordlists.get_patterns("publisher_suffixes")
        return []

    @cached_property
    def publisher_suffix_regex(self) -> str:
        """Publisher suffix regex pattern"""
        suffixes = self.publisher_suffixes
        if suffixes:
            pattern_parts = []
            for suffix in suffixes:
                if suffix in ["publisher", "book"]:
                    pattern_parts.append(f"{suffix}s?")
                else:
                    pattern_parts.append(suffix)
            return r"\b(" + "|".join(pattern_parts) + r")\b"
        return ""

    @cached_property
    def title_processing(self) -> dict[str, list[str] | dict[str, str]]:
        """Title processing configuration"""
        return {
            "stopwords": list(self.title_stopwords),
            "abbreviations": self.abbreviations,
            "generic_patterns": list(self.generic_title_patterns),
        }

    @cached_property
    def author_processing(self) -> dict[str, list[str] | dict[str, str]]:
        """Author processing configuration"""
        return {
            "stopwords": list(self.author_stopwords),
            "titles": self._wordlists.get_patterns("author_titles") if self._wordlists else [],
            "abbreviations": self.abbreviations,
        }

    def get_combined_stopwords(self, *categories: str) -> set[str]:
        """Get combined stopwords from multiple categories"""
        result = set()
        if self._wordlists:
            for category in categories:
                result.update(self._wordlists.get_stopwords(category))
        return result


# Global default instance
_default_config: ConfigLoader | None = None


def get_config(config_path: str | None = None) -> ConfigLoader:
    """Get configuration loader instance

    Args:
        config_path: Path to configuration file, None for default

    Returns:
        ConfigLoader instance
    """
    global _default_config

    if config_path:
        return ConfigLoader(config_path)

    if _default_config is None:
        _default_config = ConfigLoader(None)

    return _default_config
