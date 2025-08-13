# marc_pd_tool/application/processing/number_normalizer.py

"""Number normalization for text processing

Handles conversion of:
- Roman numerals to Arabic (XIV → 14)
- Ordinals to numbers (1st → 1, first → 1)
- Word numbers to digits (twenty-one → 21)
"""

# Standard library imports
from re import IGNORECASE
from re import sub

# Local imports
from marc_pd_tool.infrastructure.config import ConfigLoader


class NumberNormalizer:
    """Handle number normalization (Roman numerals, ordinals, word numbers)

    This functionality was lost during the August 14 refactoring and is being restored.
    """

    def __init__(self, config: ConfigLoader | None = None) -> None:
        """Initialize with configuration

        Args:
            config: Configuration loader, uses default if None
        """
        self.config = config or ConfigLoader()
        self._load_number_mappings()

    def _load_number_mappings(self) -> None:
        """Load number normalization mappings from wordlists.json"""
        # Load from wordlists.json via the Pydantic model
        wordlists = self.config.wordlists
        number_norm = wordlists.number_normalization if wordlists else None

        if not number_norm:
            # Initialize empty mappings if not found
            self.roman_numerals = {}
            self.ordinals = {}
            self.word_numbers = {}
            return

        # Get Roman numeral mappings directly from the Pydantic model
        self.roman_numerals = number_norm.roman_numerals or {}

        # Get ordinal mappings for each language
        self.ordinals = number_norm.ordinals or {}

        # Get word number mappings for each language
        self.word_numbers = number_norm.word_numbers or {}

    def normalize_numbers(self, text: str, language: str = "eng") -> str:
        """Normalize all number formats in text

        Args:
            text: Text containing numbers in various formats
            language: Language code for ordinal/word number processing

        Returns:
            Text with normalized numbers
        """
        if not text:
            return ""

        text = self._normalize_roman(text)
        text = self._normalize_ordinals(text, language)
        text = self._normalize_word_numbers(text, language)
        return text

    def _normalize_roman(self, text: str) -> str:
        """Convert Roman numerals to Arabic numbers

        Args:
            text: Text potentially containing Roman numerals

        Returns:
            Text with Roman numerals converted to Arabic
        """
        if not self.roman_numerals:
            return text

        # Convert text to lowercase for matching but preserve original case structure
        result = text
        for roman, arabic in self.roman_numerals.items():
            # Use word boundaries to avoid partial matches, case-insensitive
            pattern = r"\b" + roman + r"\b"
            result = sub(pattern, arabic, result, flags=IGNORECASE)

        return result

    def _normalize_ordinals(self, text: str, language: str) -> str:
        """Normalize ordinal numbers (1st → 1, first → 1)

        Args:
            text: Text containing ordinal numbers
            language: Language code for ordinal mappings

        Returns:
            Text with normalized ordinals
        """
        if language not in self.ordinals:
            return text

        # First normalize word ordinals (first → 1st, second → 2nd, etc.)
        ordinal_map = self.ordinals[language]
        for word_ordinal, digit_ordinal in ordinal_map.items():
            pattern = r"\b" + word_ordinal + r"\b"
            text = sub(pattern, digit_ordinal, text, flags=IGNORECASE)

        # Then normalize digit ordinals to plain numbers (1st → 1, 2nd → 2, etc.)
        # This handles both the converted ones and any that were already in digit form
        text = sub(r"\b(\d+)(?:st|nd|rd|th)\b", r"\1", text, flags=IGNORECASE)
        # Also handle language-specific ordinal suffixes
        text = sub(r"\b(\d+)(?:er|ère|e|º|ª|\.)\b", r"\1", text, flags=IGNORECASE)

        return text

    def _normalize_word_numbers(self, text: str, language: str) -> str:
        """Convert word numbers to digits (twenty-one → 21)

        Args:
            text: Text containing word numbers
            language: Language code for word number mappings

        Returns:
            Text with word numbers converted to digits
        """
        if language not in self.word_numbers:
            return text

        word_map = self.word_numbers[language]
        for word, digit in word_map.items():
            pattern = r"\b" + word + r"\b"
            text = sub(pattern, digit, text, flags=IGNORECASE)

        return text
