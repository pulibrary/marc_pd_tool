"""Generic title detection for improved matching accuracy"""

# Standard library imports
from collections import Counter
from collections import OrderedDict
from typing import Dict
from typing import Optional
from typing import Set

# Local imports
from marc_pd_tool.config_loader import get_config
from marc_pd_tool.text_utils import normalize_text


class LRUCache:
    """Simple LRU cache with size limit"""
    
    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self.cache = OrderedDict()
    
    def get(self, key: str) -> Optional[bool]:
        """Get value from cache, moving to end if found"""
        if key in self.cache:
            # Move to end (most recently used)
            self.cache.move_to_end(key)
            return self.cache[key]
        return None
    
    def put(self, key: str, value: bool) -> None:
        """Put value in cache, evicting oldest if needed"""
        if key in self.cache:
            # Update existing key
            self.cache[key] = value
            self.cache.move_to_end(key)
        else:
            # Add new key
            self.cache[key] = value
            if len(self.cache) > self.max_size:
                # Remove oldest item
                self.cache.popitem(last=False)
    
    def clear(self) -> None:
        """Clear the cache"""
        self.cache.clear()
    
    def size(self) -> int:
        """Get current cache size"""
        return len(self.cache)


class GenericTitleDetector:
    """Detects generic titles that should have reduced weight in similarity scoring"""

    # fmt: off
    # Predefined patterns for generic titles
    GENERIC_PATTERNS = {
        # Complete collections
        "collected works", "complete works", "selected works", "works",
        "collected writings", "complete writings", "selected writings",
        "collected papers", "selected papers", "papers",
        
        # Genre-specific collections
        "poems", "poetry", "selected poems", "complete poems", "collected poems",
        "essays", "selected essays", "complete essays", "collected essays",
        "stories", "short stories", "selected stories", "collected stories",
        "plays", "dramas", "selected plays", "complete plays", "collected plays",
        "letters", "correspondence", "selected letters", "collected letters",
        "speeches", "addresses", "selected speeches", "collected speeches",
        "novels", "selected novels", "collected novels",
        
        # Generic descriptors
        "anthology", "collection", "selections", "miscellany",
        "writings", "documents", "memoirs", "autobiography",
        "biography", "journal", "diary", "notebook",
        
        # Academic/professional
        "proceedings", "transactions", "bulletin", "journal",
        "report", "reports", "studies", "papers",
        "articles", "documents", "records",
        
        # Single genre words (very generic)
        "poems", "essays", "stories", "plays", "letters", "novels"
    }
    # fmt: on

    def __init__(
        self, frequency_threshold: int = 10, custom_patterns: Optional[Set[str]] = None, 
        config=None, cache_size: int = 1000, max_title_counts: int = 50000
    ):
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
        self.title_counts = Counter()
        self.detection_cache = LRUCache(cache_size)  # Bounded cache for detection results

        # Get configuration
        if config is None:
            config = get_config()
        self.config = config

        # Combine default patterns with custom ones
        self.patterns = self.GENERIC_PATTERNS.copy()
        if custom_patterns:
            self.patterns.update(custom_patterns)

    def add_title(self, title: str) -> None:
        """Add a title to frequency tracking

        Args:
            title: The title to track
        """
        if not title:
            return

        normalized = normalize_text(title)
        if normalized:
            self.title_counts[normalized] += 1
            
            # Prevent unbounded growth by cleaning up when limit is reached
            if len(self.title_counts) > self.max_title_counts:
                self._cleanup_title_counts()

    def is_generic(self, title: str, language_code: str = "") -> bool:
        """Determine if a title is generic using hybrid detection

        Args:
            title: The title to check
            language_code: MARC language code (e.g., 'eng', 'fre', 'ger')

        Returns:
            True if the title is considered generic
        """
        if not title:
            return False

        # Only apply generic detection to English titles
        if not self._is_english_language(language_code):
            return False

        normalized = normalize_text(title)
        if not normalized:
            return False

        # Check cache first
        cache_key = f"{normalized}|{language_code}"
        cached_result = self.detection_cache.get(cache_key)
        if cached_result is not None:
            return cached_result

        # Perform detection
        is_generic = self._detect_generic(normalized)

        # Cache result
        self.detection_cache.put(cache_key, is_generic)

        return is_generic

    def get_detection_reason(self, title: str, language_code: str = "") -> str:
        """Get the reason why a title was detected as generic

        Args:
            title: The title to check
            language_code: MARC language code (e.g., 'eng', 'fre', 'ger')

        Returns:
            String describing the detection reason
        """
        if not title:
            return "empty"

        # Check if language is non-English
        if not self._is_english_language(language_code):
            return (
                f"skipped_non_english_{language_code}"
                if language_code
                else "skipped_non_english_unknown"
            )

        normalized = normalize_text(title)
        if not normalized:
            return "empty"

        # Check pattern matching
        if self._is_pattern_match(normalized):
            return "pattern"

        # Check frequency
        if self._is_frequency_match(normalized):
            return "frequency"

        # Check linguistic patterns
        if self._is_linguistic_match(normalized):
            return "linguistic"

        return "none"

    def _detect_generic(self, normalized_title: str) -> bool:
        """Internal method to detect generic titles

        Args:
            normalized_title: Pre-normalized title text

        Returns:
            True if generic
        """
        # Method 1: Pattern matching (high confidence)
        if self._is_pattern_match(normalized_title):
            return True

        # Method 2: Frequency analysis (medium confidence)
        if self._is_frequency_match(normalized_title):
            return True

        # Method 3: Linguistic patterns (low confidence)
        if self._is_linguistic_match(normalized_title):
            return True

        return False

    def _is_pattern_match(self, normalized_title: str) -> bool:
        """Check if title matches known generic patterns

        Args:
            normalized_title: Pre-normalized title text

        Returns:
            True if matches a pattern
        """
        # Check for exact matches
        if normalized_title in self.patterns:
            return True

        # Check for substring matches (only for short titles)
        words = normalized_title.split()
        if len(words) <= 3:
            for pattern in self.patterns:
                if pattern in normalized_title:
                    return True

        return False

    def _is_frequency_match(self, normalized_title: str) -> bool:
        """Check if title appears frequently (likely generic)

        Args:
            normalized_title: Pre-normalized title text

        Returns:
            True if appears frequently
        """
        return self.title_counts.get(normalized_title, 0) > self.frequency_threshold

    def _is_linguistic_match(self, normalized_title: str) -> bool:
        """Check for linguistic patterns suggesting generic titles

        Args:
            normalized_title: Pre-normalized title text

        Returns:
            True if linguistic patterns suggest generic title
        """
        words = normalized_title.split()

        if not words:
            return False

        # Very short titles with only genre words
        if len(words) <= 2:
            genre_terms = {
                "poems",
                "essays",
                "stories",
                "plays",
                "letters",
                "works",
                "novels",
                "writings",
                "papers",
                "speeches",
                "addresses",
            }
            if all(word in genre_terms for word in words):
                return True

        # High stopword ratio (mostly articles/prepositions) in short titles
        if len(words) <= 4:
            stopword_count = sum(1 for word in words if word in self.config.get_stopwords())
            stopword_ratio = stopword_count / len(words)
            if stopword_ratio > 0.6:
                return True

        return False

    def _cleanup_title_counts(self) -> None:
        """Clean up title counts by keeping only the most frequent titles"""
        # Keep top 80% of the limit to avoid frequent cleanups
        keep_count = int(self.max_title_counts * 0.8)
        
        # Get the most common titles
        most_common = self.title_counts.most_common(keep_count)
        
        # Replace the counter with only the most frequent titles
        self.title_counts = Counter(dict(most_common))
        
        # Clear the detection cache since frequency data changed
        self.detection_cache.clear()

    def get_stats(self) -> Dict:
        """Get detection statistics

        Returns:
            Dictionary with detection statistics
        """
        total_titles = len(self.title_counts)
        generic_by_frequency = sum(
            1 for count in self.title_counts.values() if count > self.frequency_threshold
        )

        return {
            "total_unique_titles": total_titles,
            "total_title_occurrences": sum(self.title_counts.values()),
            "generic_patterns_count": len(self.patterns),
            "frequency_threshold": self.frequency_threshold,
            "generic_by_frequency": generic_by_frequency,
            "cache_size": self.detection_cache.size(),
            "max_cache_size": self.detection_cache.max_size,
            "max_title_counts": self.max_title_counts,
            "most_common_titles": self.title_counts.most_common(10),
        }

    def _is_english_language(self, language_code: str) -> bool:
        """Check if language code indicates English

        Args:
            language_code: MARC language code

        Returns:
            True if English or unspecified (defaults to English patterns)
        """
        if not language_code:
            # No language specified - default to English patterns
            return True

        # Check for English language codes
        english_codes = {"eng", "en"}
        return language_code.lower() in english_codes

    def reset_frequencies(self) -> None:
        """Reset frequency tracking (useful for testing)"""
        self.title_counts.clear()
        self.detection_cache.clear()
