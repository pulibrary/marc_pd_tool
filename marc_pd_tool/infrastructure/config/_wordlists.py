# marc_pd_tool/infrastructure/config/_wordlists.py

"""Pydantic models for wordlists configuration"""

# Standard library imports
import json
from pathlib import Path

# Third party imports
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field


class AbbreviationsConfig(BaseModel):
    """Abbreviations configuration"""

    bibliographic: dict[str, str] = Field(default_factory=dict)


class StopwordsConfig(BaseModel):
    """Stopwords configuration by category"""

    general: list[str] = Field(default_factory=list)
    publisher: list[str] = Field(default_factory=list)
    edition: list[str] = Field(default_factory=list)
    author: list[str] = Field(default_factory=list)
    title: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="allow")  # Allow additional stopword categories


class PatternsConfig(BaseModel):
    """Pattern lists configuration"""

    generic_titles: list[str] = Field(default_factory=list)
    ordinals: list[str] = Field(default_factory=list)
    author_titles: list[str] = Field(default_factory=list)
    publisher_suffixes: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="allow")  # Allow additional pattern types


class TextFixesConfig(BaseModel):
    """Text fixes configuration"""

    unicode_corrections: dict[str, str] = Field(default_factory=dict)

    model_config = ConfigDict(extra="allow")


class NumberNormalizationConfig(BaseModel):
    """Number normalization configuration"""

    roman_numerals: dict[str, str] = Field(default_factory=dict)
    ordinals: dict[str, dict[str, str]] = Field(default_factory=dict)
    word_numbers: dict[str, dict[str, str]] = Field(default_factory=dict)

    model_config = ConfigDict(extra="allow")


class WordlistsConfig(BaseModel):
    """Root wordlists configuration model"""

    abbreviations: AbbreviationsConfig = Field(default_factory=AbbreviationsConfig)
    stopwords: StopwordsConfig = Field(default_factory=StopwordsConfig)
    patterns: PatternsConfig = Field(default_factory=PatternsConfig)
    text_fixes: TextFixesConfig = Field(default_factory=TextFixesConfig)
    number_normalization: NumberNormalizationConfig = Field(
        default_factory=NumberNormalizationConfig
    )

    @classmethod
    def load(cls, wordlists_path: Path | str | None = None) -> "WordlistsConfig":
        """Load wordlists from JSON file

        Args:
            wordlists_path: Path to wordlists.json file

        Returns:
            Validated WordlistsConfig instance
        """
        if wordlists_path is None:
            return cls()  # Return defaults

        if isinstance(wordlists_path, str):
            wordlists_path = Path(wordlists_path)

        if wordlists_path.exists():
            try:
                with open(wordlists_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return cls.model_validate(data)
            except Exception as e:
                # Standard library imports
                import logging

                logging.getLogger(__name__).warning(
                    f"Failed to load wordlists from {wordlists_path}: {e}. Using defaults."
                )

        return cls()  # Return defaults

    def get_stopwords(self, category: str) -> list[str]:
        """Get stopwords for a category

        Args:
            category: Stopword category name

        Returns:
            List of stopwords
        """
        stopwords_dict = self.stopwords.model_dump()
        return stopwords_dict.get(category, [])

    def get_all_stopwords(self) -> set[str]:
        """Get all stopwords from all categories

        Returns:
            Set of all stopwords
        """
        all_words = set()
        for words in self.stopwords.model_dump().values():
            if isinstance(words, list):
                all_words.update(words)
        return all_words

    def get_patterns(self, pattern_type: str) -> list[str]:
        """Get patterns by type

        Args:
            pattern_type: Pattern type name

        Returns:
            List of patterns
        """
        patterns_dict = self.patterns.model_dump()
        return patterns_dict.get(pattern_type, [])

    def get_abbreviations(self) -> dict[str, str]:
        """Get bibliographic abbreviations

        Returns:
            Dictionary of abbreviations
        """
        return self.abbreviations.bibliographic

    def get_unicode_corrections(self) -> dict[str, str]:
        """Get unicode corrections

        Returns:
            Dictionary of corrections
        """
        return self.text_fixes.unicode_corrections
