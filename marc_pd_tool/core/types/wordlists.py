# marc_pd_tool/core/types/wordlists.py

"""Wordlist-related TypedDict definitions"""

# Standard library imports
from typing import TypedDict


class Abbreviations(TypedDict):
    """Type for abbreviations section"""

    bibliographic: dict[str, str]


class TextFixes(TypedDict):
    """Type for text fixes section"""

    unicode_corrections: dict[str, str]


class Wordlists(TypedDict):
    """Type for wordlists configuration"""

    abbreviations: Abbreviations
    stopwords: dict[str, list[str]]
    patterns: dict[str, list[str]]
    text_fixes: TextFixes


__all__ = ["Abbreviations", "TextFixes", "Wordlists"]
