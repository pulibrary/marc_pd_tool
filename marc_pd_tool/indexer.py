"""Multi-key indexing system for fast publication matching"""

# Standard library imports
from collections import defaultdict
from re import sub
from typing import Dict
from typing import List
from typing import Set
from typing import Tuple

# Third party imports
# (none currently needed)

# Local imports
from marc_pd_tool.enums import AuthorType
from marc_pd_tool.publication import Publication

# Common stopwords to filter from titles
STOPWORDS = {
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
    "the",
}

# Common title prefixes to normalize
TITLE_PREFIXES = {"the", "a", "an"}


def normalize_text(text: str) -> str:
    """Normalize text for indexing by removing punctuation and converting to lowercase"""
    if not text:
        return ""

    # Convert to lowercase and remove punctuation except spaces and hyphens
    normalized = sub(r"[^\w\s\-]", " ", text.lower())
    # Normalize whitespace and hyphens
    normalized = sub(r"[\s\-]+", " ", normalized)
    return normalized.strip()


def extract_significant_words(text: str, max_words: int = 5) -> List[str]:
    """Extract significant words from text, filtering stopwords"""
    if not text:
        return []

    normalized = normalize_text(text)
    words = normalized.split()

    # Filter stopwords and short words (length >= 3)
    significant = [w for w in words if w not in STOPWORDS and len(w) >= 3]
    if not significant and words:
        # If all words were filtered, keep the first word with length >= 2
        significant = [w for w in words if len(w) >= 2][:1]

    return significant[:max_words]


def generate_title_keys(title: str) -> Set[str]:
    """Generate multiple indexing keys for a title"""
    if not title:
        return set()

    keys = set()
    words = extract_significant_words(title, max_words=4)

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


def generate_author_keys(author: str, author_type: AuthorType = AuthorType.UNKNOWN) -> Set[str]:
    """Generate multiple indexing keys for an author name based on author type

    Args:
        author: The author name string
        author_type: The type of author (PERSONAL, CORPORATE, MEETING, or UNKNOWN)

    Returns:
        Set of indexing keys appropriate for the author type
    """
    if not author:
        return set()

    keys = set()
    author_lower = author.lower().strip()

    if author_type == AuthorType.PERSONAL:
        # Personal names: use surname/given name parsing
        keys = _generate_personal_name_keys(author_lower)
    elif author_type == AuthorType.CORPORATE:
        # Corporate names: use entity-based parsing
        keys = _generate_corporate_name_keys(author_lower)
    elif author_type == AuthorType.MEETING:
        # Meeting names: use entity-based parsing
        keys = _generate_meeting_name_keys(author_lower)
    else:
        # Unknown type: fall back to personal name parsing (backward compatibility)
        keys = _generate_personal_name_keys(author_lower)

    # Note: Metaphone keys removed to reduce false positives

    return keys


def _generate_personal_name_keys(author_lower: str) -> Set[str]:
    """Generate keys for personal names (field 100)

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


def _generate_corporate_name_keys(author_lower: str) -> Set[str]:
    """Generate keys for corporate names (field 110)

    Returns:
        Set of keys for indexing
    """
    keys = set()

    # Extract significant words from the corporate name
    words = extract_significant_words(author_lower, max_words=6)

    # Add individual words
    for word in words:
        if len(word) >= 3:
            keys.add(word)

    # Add 2-word combinations for key corporate terms
    if len(words) >= 2:
        for i in range(len(words) - 1):
            keys.add(f"{words[i]}_{words[i+1]}")

    # Add 3-word combinations for longer corporate names
    if len(words) >= 3:
        for i in range(len(words) - 2):
            keys.add(f"{words[i]}_{words[i+1]}_{words[i+2]}")

    return keys


def _generate_meeting_name_keys(author_lower: str) -> Set[str]:
    """Generate keys for meeting names (field 111)

    Returns:
        Set of keys for indexing
    """
    keys = set()

    # Extract significant words from the meeting name
    words = extract_significant_words(author_lower, max_words=6)

    # Add individual words
    for word in words:
        if len(word) >= 3:
            keys.add(word)

    # Add 2-word combinations for key meeting terms
    if len(words) >= 2:
        for i in range(len(words) - 1):
            keys.add(f"{words[i]}_{words[i+1]}")

    # Add 3-word combinations for longer meeting names
    if len(words) >= 3:
        for i in range(len(words) - 2):
            keys.add(f"{words[i]}_{words[i+1]}_{words[i+2]}")

    return keys


class PublicationIndex:
    """Multi-key index for fast publication lookups"""

    def __init__(self):
        self.title_index: Dict[str, Set[int]] = defaultdict(set)
        self.author_index: Dict[str, Set[int]] = defaultdict(set)
        self.year_index: Dict[int, Set[int]] = defaultdict(set)
        self.publications: List[Publication] = []

    def add_publication(self, pub: Publication) -> int:
        """Add a publication to the index and return its ID"""
        pub_id = len(self.publications)
        self.publications.append(pub)

        # Index by title
        title_keys = generate_title_keys(pub.title)
        for key in title_keys:
            self.title_index[key].add(pub_id)

        # Index by author
        if pub.author:
            author_keys = generate_author_keys(pub.author, pub.author_type)
            for key in author_keys:
                self.author_index[key].add(pub_id)

        # Index by year
        if pub.year:
            self.year_index[pub.year].add(pub_id)

        return pub_id

    def find_candidates(self, query_pub: Publication, year_tolerance: int = 2) -> Set[int]:
        """Find candidate publication IDs that might match the query"""
        candidates = set()

        # Find candidates by title
        title_keys = generate_title_keys(query_pub.title)
        title_candidates = set()
        for key in title_keys:
            title_candidates.update(self.title_index.get(key, set()))

        # Find candidates by author (if available)
        author_candidates = set()
        if query_pub.author:
            author_keys = generate_author_keys(query_pub.author, query_pub.author_type)
            for key in author_keys:
                author_candidates.update(self.author_index.get(key, set()))

        # Find candidates by year (within tolerance)
        year_candidates = set()
        if query_pub.year:
            for year_offset in range(-year_tolerance, year_tolerance + 1):
                target_year = query_pub.year + year_offset
                year_candidates.update(self.year_index.get(target_year, set()))

        # Combine candidates with priority
        if title_candidates:
            candidates.update(title_candidates)

            # If we have both title and author candidates, prefer intersection
            if author_candidates:
                intersection = title_candidates & author_candidates
                if intersection:
                    candidates = intersection
                else:
                    # No intersection, but add author candidates too
                    candidates.update(author_candidates)
        elif author_candidates:
            # No title candidates, use author candidates
            candidates.update(author_candidates)

        # Filter by year if we have year info
        if year_candidates and candidates:
            candidates &= year_candidates
        elif year_candidates and not candidates:
            # If no title/author candidates but year candidates exist, use them
            candidates = year_candidates

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
            "year_keys": len(self.year_index),
            "avg_title_keys_per_pub": len(self.title_index) / max(1, len(self.publications)),
            "avg_author_keys_per_pub": len(self.author_index) / max(1, len(self.publications)),
        }


def build_index(publications: List[Publication]) -> PublicationIndex:
    """Build a complete index from a list of publications"""
    index = PublicationIndex()
    for pub in publications:
        index.add_publication(pub)
    return index
