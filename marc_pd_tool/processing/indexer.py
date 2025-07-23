"""Multi-key indexing system for fast publication matching"""

# Standard library imports
from collections import defaultdict
from typing import Dict
from typing import List
from typing import Set
from typing import Tuple
from typing import Union

# Local imports
from marc_pd_tool.data.publication import Publication
from marc_pd_tool.infrastructure.config_loader import get_config
from marc_pd_tool.utils.text_utils import extract_significant_words
from marc_pd_tool.utils.text_utils import normalize_text


class CompactIndexEntry:
    """Memory-efficient container for index entries - stores single int or set"""

    __slots__ = ("_data",)

    def __init__(self):
        self._data = None  # None, int, or set

    def add(self, pub_id: int) -> None:
        """Add a publication ID to this entry"""
        if self._data is None:
            # First entry - store as single int
            self._data = pub_id
        elif isinstance(self._data, int):
            # Second entry - convert to set
            if self._data != pub_id:  # Only convert if different
                self._data = {self._data, pub_id}
        else:
            # Already a set - add to it
            self._data.add(pub_id)

    def get_ids(self) -> Set[int]:
        """Get all publication IDs as a set"""
        if self._data is None:
            return set()
        elif isinstance(self._data, int):
            return {self._data}
        else:
            return self._data.copy()

    def is_empty(self) -> bool:
        """Check if entry is empty"""
        return self._data is None


def generate_title_keys(title: str, stopwords: set) -> Set[str]:
    """Generate multiple indexing keys for a title"""
    if not title:
        return set()

    keys = set()
    words = extract_significant_words(title, stopwords, max_words=4)

    if not words:
        return set()

    # Single word keys (for exact word matches)
    for word in words:
        if len(word) >= 3:  # Only index words with 3+ characters
            keys.add(word)

    # Multi-word combinations
    if len(words) >= 2:
        # First two words
        keys.add("_".join(words[:2]))
        # Last two words
        if len(words) > 2:
            keys.add("_".join(words[-2:]))
        # First three words
        if len(words) >= 3:
            keys.add("_".join(words[:3]))

    # Note: Metaphone keys removed to reduce false positives

    return keys


def generate_author_keys(author: str) -> Set[str]:
    """Generate multiple indexing keys for an author name

    Args:
        author: The author name string

    Returns:
        Set of indexing keys for the author
    """
    if not author:
        return set()

    keys = set()
    author_lower = author.lower().strip()

    # Use personal name parsing strategy for all authors
    # since 245$c typically contains personal names
    keys = _generate_personal_name_keys(author_lower)

    # Note: Metaphone keys removed to reduce false positives

    return keys


def _generate_personal_name_keys(author_lower: str) -> Set[str]:
    """Generate keys for author names (using personal name parsing strategy)

    Returns:
        Set of keys for indexing
    """
    keys = set()

    # Handle common author formats: "Last, First" or "First Last"
    if "," in author_lower:
        # Format: "Last, First Middle"
        parts = [p.strip() for p in author_lower.split(",")]
        if len(parts) >= 2:
            surname = normalize_text(parts[0]).strip()
            given_names = normalize_text(parts[1]).split()

            # Surname only (always include)
            if surname and len(surname) >= 2:
                keys.add(surname)

            # Surname + first name (use first given name)
            if given_names and surname:
                keys.add(f"{surname}_{given_names[0]}")

            # Surname + first initial
            if given_names and surname and len(given_names[0]) > 0:
                keys.add(f"{surname}_{given_names[0][0]}")

            # Reversed: First Last (use first given name)
            if given_names and surname:
                keys.add(f"{given_names[0]}_{surname}")

            # Add individual given names for matching
            for given in given_names:
                if len(given) >= 2:
                    keys.add(given)
    else:
        # Format: "First Middle Last" or single name
        words = normalize_text(author_lower).split()
        if words:
            # Last word as surname (always include)
            if len(words[-1]) >= 2:
                keys.add(words[-1])

            # First word + last word
            if len(words) >= 2 and len(words[0]) >= 2:
                keys.add(f"{words[0]}_{words[-1]}")
                keys.add(f"{words[-1]}_{words[0]}")

            # Handle initials (F. Scott -> f_scott, scott_f, also scott, f, scott)
            if len(words) >= 2:
                # Add individual words for matching
                for word in words:
                    # Remove periods from initials and add if long enough
                    clean_word = word.replace(".", "")
                    if len(clean_word) >= 1:  # Allow single letters for initials
                        keys.add(clean_word)

                # First word + last initial
                if len(words[0]) >= 1:
                    keys.add(f"{words[-1]}_{words[0].replace('.', '')}")

            # For single names
            if len(words) == 1 and len(words[0]) >= 2:
                keys.add(words[0])

    return keys


def generate_publisher_keys(
    publisher: str, publishing_stopwords: set, general_stopwords: set
) -> Set[str]:
    """Generate multiple indexing keys for a publisher name

    Args:
        publisher: The publisher name string
        publishing_stopwords: Set of publisher-specific stopwords
        general_stopwords: Set of general stopwords

    Returns:
        Set of indexing keys for the publisher
    """
    if not publisher:
        return set()

    keys = set()

    # Normalize the publisher name
    normalized = normalize_text(publisher)
    words = normalized.split()

    if not words:
        return set()

    # Filter out publishing stopwords but keep at least some words
    significant_words = [w for w in words if w not in publishing_stopwords and len(w) >= 3]
    if not significant_words and words:
        # If all words were filtered, keep the longest non-stopword words
        significant_words = [w for w in words if w not in general_stopwords and len(w) >= 3][:3]

    # Single word keys (for exact word matches)
    for word in significant_words:
        if len(word) >= 3:
            keys.add(word)

    # Multi-word combinations for better matching
    if len(significant_words) >= 2:
        # First two significant words
        keys.add("_".join(significant_words[:2]))
        # Last two significant words
        if len(significant_words) > 2:
            keys.add("_".join(significant_words[-2:]))
        # First three significant words
        if len(significant_words) >= 3:
            keys.add("_".join(significant_words[:3]))

    # Add full normalized name (without publishing stopwords) as a key
    if significant_words:
        keys.add("_".join(significant_words))

    return keys


def generate_edition_keys(edition: str, edition_stopwords: set, ordinal_terms: set) -> Set[str]:
    """Generate multiple indexing keys for an edition statement

    Args:
        edition: The edition statement string (e.g., "2nd ed.", "First edition", "Rev. ed.")
        edition_stopwords: Set of edition-specific stopwords
        ordinal_terms: Set of ordinal terms to recognize

    Returns:
        Set of indexing keys for the edition
    """
    if not edition:
        return set()

    keys = set()

    # Normalize the edition statement
    normalized = normalize_text(edition)
    words = normalized.split()

    if not words:
        return set()

    # Extract significant words for edition matching
    significant_words = [w for w in words if w not in edition_stopwords and len(w) >= 2]

    for word in words:
        clean_word = word.replace(".", "").replace(",", "").lower()
        if clean_word in ordinal_terms or clean_word.isdigit():
            keys.add(clean_word)

    # Add significant words
    for word in significant_words:
        if len(word) >= 2:
            keys.add(word)

    # Add combination keys for multi-word editions
    if len(significant_words) >= 2:
        keys.add("_".join(significant_words[:2]))

    # Add full normalized edition (without stopwords) as a key
    if significant_words:
        keys.add("_".join(significant_words))

    return keys


class PublicationIndex:
    """Multi-key index for fast publication lookups"""

    def __init__(self, config=None):
        self.title_index: Dict[str, CompactIndexEntry] = {}
        self.author_index: Dict[str, CompactIndexEntry] = {}
        self.publisher_index: Dict[str, CompactIndexEntry] = {}
        self.edition_index: Dict[str, CompactIndexEntry] = {}
        self.year_index: Dict[int, CompactIndexEntry] = {}
        self.publications: List[Publication] = []

        # Cache configuration to avoid repeated loading
        if config is None:
            config = get_config()
        self.config = config

        # Pre-fetch word lists for performance
        self.stopwords = config.get_stopwords()
        self.publisher_stopwords = config.get_publisher_stopwords()
        self.edition_stopwords = config.get_edition_stopwords()
        self.ordinal_terms = config.get_ordinal_terms()

    def add_publication(self, pub: Publication) -> int:
        """Add a publication to the index and return its ID"""
        pub_id = len(self.publications)
        self.publications.append(pub)

        # Index by title - now includes all title components (a,b,n,p) from MARC
        title_keys = generate_title_keys(pub.title, self.stopwords)
        for key in title_keys:
            if key not in self.title_index:
                self.title_index[key] = CompactIndexEntry()
            self.title_index[key].add(pub_id)

        # Index by author - index both 245$c and 1xx fields
        if pub.author:
            author_keys = generate_author_keys(pub.author)
            for key in author_keys:
                if key not in self.author_index:
                    self.author_index[key] = CompactIndexEntry()
                self.author_index[key].add(pub_id)

        # Also index main author (1xx fields) if available
        if pub.main_author:
            main_author_keys = generate_author_keys(pub.main_author)
            for key in main_author_keys:
                if key not in self.author_index:
                    self.author_index[key] = CompactIndexEntry()
                self.author_index[key].add(pub_id)

        # Index by publisher
        if pub.publisher:
            publisher_keys = generate_publisher_keys(
                pub.publisher, self.publisher_stopwords, self.stopwords
            )
            for key in publisher_keys:
                if key not in self.publisher_index:
                    self.publisher_index[key] = CompactIndexEntry()
                self.publisher_index[key].add(pub_id)

        # Index by edition (gracefully handle missing edition data)
        if pub.edition:
            edition_keys = generate_edition_keys(
                pub.edition, self.edition_stopwords, self.ordinal_terms
            )
            for key in edition_keys:
                if key not in self.edition_index:
                    self.edition_index[key] = CompactIndexEntry()
                self.edition_index[key].add(pub_id)

        # Index by year
        if pub.year:
            if pub.year not in self.year_index:
                self.year_index[pub.year] = CompactIndexEntry()
            self.year_index[pub.year].add(pub_id)

        return pub_id

    def find_candidates(self, query_pub: Publication, year_tolerance: int = 2) -> Set[int]:
        """Find candidate publication IDs that might match the query"""
        candidates = set()

        # Find candidates by title - now includes all title components (a,b,n,p) from MARC
        title_keys = generate_title_keys(query_pub.title, self.stopwords)
        title_candidates = set()
        for key in title_keys:
            entry = self.title_index.get(key)
            if entry and not entry.is_empty():
                title_candidates.update(entry.get_ids())

        # Find candidates by author (if available) - search both author fields
        author_candidates = set()
        if query_pub.author:
            author_keys = generate_author_keys(query_pub.author)
            for key in author_keys:
                entry = self.author_index.get(key)
                if entry and not entry.is_empty():
                    author_candidates.update(entry.get_ids())

        # Also search by main author if available
        if query_pub.main_author:
            main_author_keys = generate_author_keys(query_pub.main_author)
            for key in main_author_keys:
                entry = self.author_index.get(key)
                if entry and not entry.is_empty():
                    author_candidates.update(entry.get_ids())

        # Find candidates by publisher (if available)
        publisher_candidates = set()
        if query_pub.publisher:
            publisher_keys = generate_publisher_keys(
                query_pub.publisher, self.publisher_stopwords, self.stopwords
            )
            for key in publisher_keys:
                entry = self.publisher_index.get(key)
                if entry and not entry.is_empty():
                    publisher_candidates.update(entry.get_ids())

        # Find candidates by edition (if available)
        edition_candidates = set()
        if query_pub.edition:
            edition_keys = generate_edition_keys(
                query_pub.edition, self.edition_stopwords, self.ordinal_terms
            )
            for key in edition_keys:
                entry = self.edition_index.get(key)
                if entry and not entry.is_empty():
                    edition_candidates.update(entry.get_ids())

        # Find candidates by year (within tolerance)
        year_candidates = set()
        if query_pub.year:
            for year_offset in range(-year_tolerance, year_tolerance + 1):
                target_year = query_pub.year + year_offset
                entry = self.year_index.get(target_year)
                if entry and not entry.is_empty():
                    year_candidates.update(entry.get_ids())

        # CRITICAL PERFORMANCE FIX: Apply year filtering FIRST
        # Year filtering is the most selective filter - should dramatically reduce search space
        if year_candidates:
            # Start with year candidates as the base (small set for narrow year ranges)
            candidates = year_candidates.copy()

            # Intersect with other candidate sets to narrow further
            if title_candidates:
                candidates &= title_candidates

                # If we still have candidates after title intersection, try author intersection
                if candidates and author_candidates:
                    title_author_intersection = candidates & author_candidates
                    if title_author_intersection:
                        candidates = title_author_intersection

                        # Try publisher intersection if we still have candidates
                        if candidates and publisher_candidates:
                            publisher_intersection = candidates & publisher_candidates
                            if publisher_intersection:
                                candidates = publisher_intersection

                                # Try edition intersection if we still have candidates
                                if candidates and edition_candidates:
                                    edition_intersection = candidates & edition_candidates
                                    if edition_intersection:
                                        candidates = edition_intersection
            elif author_candidates:
                # No title candidates, but intersect year with author
                candidates &= author_candidates
            elif publisher_candidates:
                # Only year and publisher
                candidates &= publisher_candidates
            elif edition_candidates:
                # Only year and edition
                candidates &= edition_candidates
            # If no other candidates, keep year candidates as-is

        else:
            # No year information - use much more restrictive fallback logic
            # Only use title candidates and only if the set is reasonably small
            if title_candidates and len(title_candidates) < 1000:
                candidates = title_candidates.copy()
                if author_candidates:
                    intersection = title_candidates & author_candidates
                    if intersection:
                        candidates = intersection
            elif author_candidates and len(author_candidates) < 500:
                candidates = author_candidates.copy()
            else:
                # Skip records that would generate too many candidates without year filtering
                candidates = set()

        return candidates

    # Metaphone-related methods removed to reduce false positives

    def get_publication(self, pub_id: int) -> Publication:
        """Get publication by ID"""
        return self.publications[pub_id]

    def get_candidates_list(
        self, query_pub: Publication, year_tolerance: int = 2
    ) -> List[Publication]:
        """Get list of candidate publications for matching"""
        candidate_ids = self.find_candidates(query_pub, year_tolerance)
        return [self.publications[pub_id] for pub_id in candidate_ids]

    # Metaphone-related methods removed to reduce false positives

    def size(self) -> int:
        """Return number of publications in index"""
        return len(self.publications)

    def get_stats(self) -> Dict[str, int]:
        """Get indexing statistics"""
        return {
            "total_publications": len(self.publications),
            "title_keys": len(self.title_index),
            "author_keys": len(self.author_index),
            "publisher_keys": len(self.publisher_index),
            "edition_keys": len(self.edition_index),
            "year_keys": len(self.year_index),
            "avg_title_keys_per_pub": len(self.title_index) / max(1, len(self.publications)),
            "avg_author_keys_per_pub": len(self.author_index) / max(1, len(self.publications)),
            "avg_publisher_keys_per_pub": (
                len(self.publisher_index) / max(1, len(self.publications))
            ),
            "avg_edition_keys_per_pub": len(self.edition_index) / max(1, len(self.publications)),
        }


def build_index(publications: List[Publication], config=None) -> PublicationIndex:
    """Build a complete index from a list of publications"""
    index = PublicationIndex(config)
    for pub in publications:
        index.add_publication(pub)
    return index
