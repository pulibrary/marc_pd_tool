# marc_pd_tool/processing/text_processing.py

"""Consolidated text processing utilities for MARC copyright analysis

This module combines:
- Language processing and stopword removal
- Multi-language stemming
- Abbreviation expansion
- Publisher extraction utilities
- Generic title detection
"""

# Standard library imports
from collections import Counter
from functools import lru_cache
from re import split as re_split
from typing import Optional  # Needed for function signatures
from typing import TYPE_CHECKING

# Third party imports
from Stemmer import Stemmer  # type: ignore[import-not-found]
from fuzzywuzzy import fuzz
from stop_words import get_stop_words

# Local imports
from marc_pd_tool.infrastructure.config_loader import get_config

if TYPE_CHECKING:
    from marc_pd_tool.infrastructure.config_loader import ConfigLoader

# Local imports
from marc_pd_tool.utils.publisher_utils import extract_publisher_candidates
from marc_pd_tool.utils.text_utils import normalize_text_comprehensive
from marc_pd_tool.utils.text_utils import normalize_unicode
from marc_pd_tool.utils.types import JSONDict
from marc_pd_tool.utils.types import StemmerDict


class LanguageProcessor:
    """Handles multilingual stopword removal"""

    def __init__(self) -> None:
        """Initialize with multilingual stopword support"""

        self.stopwords = {
            "eng": set(get_stop_words("en")),
            "fre": set(get_stop_words("fr")),
            "ger": set(get_stop_words("de")),
            "spa": set(get_stop_words("es")),
            "ita": set(get_stop_words("it")),
        }

    def remove_stopwords(self, text: str, language: str = "eng") -> list[str]:
        """Remove stopwords from text and return significant words

        Args:
            text: Input text to process
            language: Language code for stopword removal

        Returns:
            List of significant words (stopwords removed)
        """
        if not text:
            return []

        # Normalize Unicode first to fix encoding issues
        text = normalize_unicode(text)

        words = text.lower().split()
        stopword_set = self.stopwords.get(language, self.stopwords["eng"])
        return [word for word in words if word not in stopword_set and len(word) >= 2]


class MultiLanguageStemmer:
    """Handles multilingual stemming for word-based matching"""

    def __init__(self) -> None:
        """Initialize stemmers for supported languages"""
        # Map language codes to PyStemmer language names
        self.language_map = {
            "eng": "english",
            "fre": "french",
            "ger": "german",
            "spa": "spanish",
            "ita": "italian",
        }

        # Initialize stemmers lazily to avoid serialization issues
        self._stemmers: Optional[StemmerDict] = None

    def _get_stemmers(self) -> dict[str, Stemmer]:
        """Lazy initialization of stemmers to avoid pickle issues"""
        if self._stemmers is None:
            self._stemmers = {}
            for lang_code, lang_name in self.language_map.items():
                try:
                    self._stemmers[lang_code] = Stemmer(lang_name)
                except KeyError:
                    # Language not supported by PyStemmer
                    pass
        return self._stemmers

    def stem_words(self, words: list[str], language: str = "eng") -> list[str]:
        """Stem a list of words in the specified language

        Args:
            words: List of words to stem
            language: Language code for stemming

        Returns:
            List of stemmed words
        """
        if not words:
            return []

        stemmers = self._get_stemmers()
        stemmer = stemmers.get(language)
        if not stemmer:
            # Fallback to English or return unstemmed
            stemmer = stemmers.get("eng")
            if not stemmer:
                return words

        return list(stemmer.stemWords(words))  # Ensure list type

    def __getstate__(self) -> JSONDict:
        """Custom pickle support - exclude C objects"""
        state = self.__dict__.copy()
        # Remove the unpicklable stemmers
        state["_stemmers"] = None
        return state

    def __setstate__(self, state: JSONDict) -> None:
        """Custom unpickle support"""
        self.__dict__.update(state)


# Get abbreviations from config
_config = get_config()
PUBLISHING_ABBREVIATIONS = _config.abbreviations
if not PUBLISHING_ABBREVIATIONS:
    raise ValueError("No abbreviations found in wordlists.json")


def expand_abbreviations(text: str) -> str:
    """Expand common abbreviations in text

    Args:
        text: Input text with potential abbreviations

    Returns:
        Text with abbreviations expanded
    """
    if not text:
        return text

    # Normalize Unicode first
    text = normalize_unicode(text)

    # Work with lowercase for matching
    text_lower = text.lower()
    words = text_lower.split()
    result_words = []

    for word in words:
        # Remove trailing punctuation for matching
        clean_word = word.rstrip(".,;:!?")

        # Check if it's an abbreviation
        if clean_word in PUBLISHING_ABBREVIATIONS:
            # Conservative expansion logic
            # Only expand if:
            # 1. The abbreviation ends with a period
            # 2. OR it's a very short abbreviation (< 5 chars)
            # 3. OR it appears at certain positions (e.g., after numbers)
            if word.endswith(".") or len(clean_word) < 5:
                expanded = PUBLISHING_ABBREVIATIONS[clean_word]
                # Preserve original punctuation
                if word != clean_word:
                    expanded += word[len(clean_word) :]
                result_words.append(expanded)
            else:
                result_words.append(word)
        else:
            result_words.append(word)

    return " ".join(result_words)


def normalize_publisher_text(
    text: str, stopwords: Optional[set[str]] = None, config: Optional["ConfigLoader"] = None
) -> str:
    """Normalize publisher text for matching

    Args:
        text: Publisher text to normalize
        stopwords: Optional set of publisher stopwords to remove
        config: Optional ConfigLoader for publisher suffix patterns

    Returns:
        Normalized publisher text
    """
    # Get publisher suffix pattern from config
    if config is None:
        config = get_config()

    suffix_pattern = config.publisher_suffix_regex

    return normalize_text_comprehensive(
        text,
        remove_brackets=False,  # Keep brackets in publisher names
        remove_punctuation=True,
        join_split_letters=True,
        lowercase=True,
        normalize_whitespace=True,
        apply_unicode_fixes=True,
        ascii_fold_chars=True,
        stopwords=stopwords,
        remove_suffixes=suffix_pattern,
    )


def _get_publisher_stopwords() -> set[str]:
    """Helper to get publisher stopwords from config

    Returns:
        Set of publisher stopwords
    """
    config = get_config()
    stopwords_list = list(config.publisher_stopwords) if config else None
    return set(stopwords_list) if stopwords_list else set()


def extract_best_publisher_match(
    marc_publisher: str | None, full_text: str, threshold: int = 80
) -> str | None:
    """Extract best matching publisher from renewal full text

    Args:
        marc_publisher: Original publisher from MARC record
        full_text: Full text field from renewal record
        threshold: Minimum fuzzy match score (0-100)

    Returns:
        Best matching publisher string or None
    """
    if not marc_publisher or not full_text:
        return None

    # Get publisher stopwords once
    stopwords = _get_publisher_stopwords()

    # Clean and prepare MARC publisher using centralized normalization
    marc_clean = normalize_publisher_text(marc_publisher, stopwords)
    if not marc_clean:
        return None

    # Extract potential publishers using centralized extraction
    candidates = extract_publisher_candidates(full_text)

    # Find best fuzzy match
    best_score = 0
    best_match = None

    for candidate in candidates:
        # Normalize candidate using same logic as MARC publisher
        candidate_clean = normalize_publisher_text(candidate, stopwords)
        score = fuzz.token_sort_ratio(marc_clean, candidate_clean)
        if score > best_score and score >= threshold:
            best_score = score
            best_match = candidate

    return best_match


# Note: LRUCache class removed in favor of functools.lru_cache


class GenericTitleDetector:
    """Detects generic titles like 'Collected Works', 'Poems', etc.

    Uses both pattern matching and frequency analysis to identify
    titles that are too generic to be reliable identifiers.
    """

    def __init__(
        self,
        frequency_threshold: int = 10,
        custom_patterns: Optional[set[str]] = None,
        config: Optional["ConfigLoader"] = None,
        cache_size: int = 1000,
        max_title_counts: int = 50000,
    ) -> None:
        """Initialize the generic title detector
        Args:
            frequency_threshold: Minimum occurrences to consider a title generic
            custom_patterns: Additional patterns to consider generic
            config: Configuration loader for accessing stopwords
            cache_size: Maximum size for detection result cache
            max_title_counts: Maximum number of titles to track in frequency counter
        """
        self.frequency_threshold = frequency_threshold
        self.max_title_counts = max_title_counts
        self.title_counts: Counter[str] = Counter()
        self.cache_size = cache_size  # Store for creating cached method

        # Get patterns from config - require config to be present
        if not config:
            config = get_config()

        generic_patterns = list(config.generic_title_patterns)
        if not generic_patterns:
            raise ValueError("No generic title patterns found in wordlists.json")

        self.patterns = set(p.lower() for p in generic_patterns)

        # Add custom patterns if provided
        if custom_patterns:
            self.patterns.update(p.lower() for p in custom_patterns)

        # Get stopwords for filtering - require config
        self.stopwords = config.stopwords_set

        self._trim_performed = False  # Track if we've trimmed the counter

        # Create cached detection method with proper maxsize
        self._is_generic_cached = lru_cache(maxsize=cache_size)(self._is_generic_impl)

    def _trim_title_counts(self) -> None:
        """Trim the counter to prevent unbounded memory growth"""
        if len(self.title_counts) > self.max_title_counts:
            # Keep only the most common titles
            self.title_counts = Counter(
                dict(self.title_counts.most_common(self.max_title_counts // 2))
            )
            self._trim_performed = True

    def add_title(self, title: str) -> None:
        """Add a title to the frequency counter

        Args:
            title: Title to add to frequency analysis
        """
        if not title:
            return

        # Normalize Unicode before processing
        title = normalize_unicode(title)

        normalized = self._normalize_title(title)
        if normalized:
            self.title_counts[normalized] += 1

            # Trim counter if it gets too large
            if len(self.title_counts) > self.max_title_counts:
                self._trim_title_counts()

    def is_generic(self, title: str, language: str = "eng") -> bool:
        """Check if a title is generic based on patterns or frequency

        Args:
            title: Title to check
            language: Language code (for future language-specific patterns)

        Returns:
            True if the title is considered generic
        """
        if not title:
            return False

        # Use cached implementation
        return self._is_generic_cached(title, language)

    def _is_generic_impl(self, title: str, language: str) -> bool:
        """Internal implementation of generic detection (cached)

        Args:
            title: Title to check
            language: Language code

        Returns:
            True if the title is considered generic
        """
        # Normalize Unicode before processing
        title = normalize_unicode(title)

        normalized = self._normalize_title(title)
        if not normalized:
            return False

        # Check pattern matching first (faster)
        if any(pattern in normalized for pattern in self.patterns):
            return True

        # Check frequency-based detection
        # Add a minimum length requirement to avoid false positives on short titles
        if len(normalized) < 20 and self.title_counts[normalized] >= self.frequency_threshold:
            return True

        return False

    def get_detection_reason(self, title: str, language: str = "eng") -> str:
        """Get the reason why a title was detected as generic

        Args:
            title: Title to check
            language: Language code

        Returns:
            String describing why the title is generic, or 'none'
        """
        if not title:
            return "none"

        # Normalize Unicode before processing
        title = normalize_unicode(title)

        normalized = self._normalize_title(title)
        if not normalized:
            return "none"

        # Check patterns first - sort by length descending to match longer patterns first
        sorted_patterns = sorted(self.patterns, key=len, reverse=True)
        for pattern in sorted_patterns:
            if pattern in normalized:
                return f"pattern: {pattern}"

        # Check frequency
        count = self.title_counts[normalized]
        if len(normalized) < 20 and count >= self.frequency_threshold:
            return f"frequency: {count} occurrences"

        return "none"

    def _normalize_title(self, title: str) -> str:
        """Normalize title for comparison

        Args:
            title: Title to normalize

        Returns:
            Normalized title string
        """
        # Basic normalization: lowercase, remove punctuation, collapse whitespace
        normalized = title.lower()
        # Remove punctuation except spaces
        words = re_split(r"[^\w\s]", normalized)
        normalized = " ".join(words)
        # Collapse multiple spaces
        normalized = " ".join(normalized.split())
        return normalized.strip()

    def get_stats(self) -> dict[str, int]:
        """Get statistics about the detector

        Returns:
            Dictionary with statistics
        """
        generic_by_freq = sum(
            1
            for title, count in self.title_counts.items()
            if len(title) < 20 and count >= self.frequency_threshold
        )

        return {
            "total_unique_titles": len(self.title_counts),
            "generic_by_frequency": generic_by_freq,
            "pattern_count": len(self.patterns),
            "frequency_threshold": self.frequency_threshold,
            "counter_trimmed": self._trim_performed,
        }

    def __getstate__(self) -> JSONDict:
        """Support pickling by excluding the cached method"""
        state = self.__dict__.copy()
        # Remove the lru_cache wrapped method which can't be pickled
        if "_is_generic_cached" in state:
            del state["_is_generic_cached"]
        return state

    def __setstate__(self, state: JSONDict) -> None:
        """Support unpickling by recreating the cached method"""
        self.__dict__.update(state)
        # Recreate the cached method
        cache_size = getattr(self, "cache_size", 1000)
        self._is_generic_cached = lru_cache(maxsize=cache_size)(self._is_generic_impl)
