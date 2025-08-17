# marc_pd_tool/core/types/wordlists.py

"""Wordlist-related type definitions using Pydantic models."""

# Standard library imports
from typing import TypedDict

# Third party imports
# Third-party imports
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field

# Configuration for wordlist models - these come from external JSON
WORDLIST_CONFIG = ConfigDict(
    strict=False,  # Allow type coercion from JSON
    validate_assignment=True,
    frozen=True,
    extra="forbid",
    str_strip_whitespace=True,
)


# Keep TypedDict versions for backward compatibility
class Abbreviations(TypedDict):
    """Type for abbreviations section (legacy)."""

    bibliographic: dict[str, str]


class TextFixes(TypedDict):
    """Type for text fixes section (legacy)."""

    unicode_corrections: dict[str, str]


class Wordlists(TypedDict):
    """Type for wordlists configuration (legacy)."""

    abbreviations: Abbreviations
    stopwords: dict[str, list[str]]
    patterns: dict[str, list[str]]
    text_fixes: TextFixes


# New Pydantic models
class AbbreviationsModel(BaseModel):
    """Pydantic model for abbreviations section."""

    model_config = WORDLIST_CONFIG

    bibliographic: dict[str, str] = Field(default_factory=dict)


class TextFixesModel(BaseModel):
    """Pydantic model for text fixes section."""

    model_config = WORDLIST_CONFIG

    unicode_corrections: dict[str, str] = Field(default_factory=dict)


class WordlistsModel(BaseModel):
    """Pydantic model for wordlists configuration."""

    model_config = WORDLIST_CONFIG

    abbreviations: AbbreviationsModel
    stopwords: dict[str, list[str]] = Field(default_factory=dict)
    patterns: dict[str, list[str]] = Field(default_factory=dict)
    text_fixes: TextFixesModel


__all__ = [
    # Legacy TypedDicts
    "Abbreviations",
    "TextFixes",
    "Wordlists",
    # New Pydantic models
    "AbbreviationsModel",
    "TextFixesModel",
    "WordlistsModel",
]
