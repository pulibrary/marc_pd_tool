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


def generate_publisher_keys(publisher: str) -> Set[str]:
    """Generate multiple indexing keys for a publisher name
    
    Args:
        publisher: The publisher name string
        
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
    
    # Remove common publishing terms that don't help with matching
    publishing_stopwords = {
        "inc", "corp", "corporation", "company", "co", "ltd", "limited", 
        "publishers", "publisher", "publishing", "publications", "press", 
        "books", "book", "house", "group", "media", "entertainment"
    }
    
    # Filter out publishing stopwords but keep at least some words
    significant_words = [w for w in words if w not in publishing_stopwords and len(w) >= 3]
    if not significant_words and words:
        # If all words were filtered, keep the longest non-stopword words
        significant_words = [w for w in words if w not in STOPWORDS and len(w) >= 3][:3]
    
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


def generate_edition_keys(edition: str) -> Set[str]:
    """Generate multiple indexing keys for an edition statement
    
    Args:
        edition: The edition statement string (e.g., "2nd ed.", "First edition", "Rev. ed.")
        
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
    
    # Remove common edition stopwords that don't help with matching
    edition_stopwords = {
        "edition", "ed", "printing", "print", "impression", "issue", "vol", "volume"
    }
    
    # Extract significant words for edition matching
    significant_words = [w for w in words if w not in edition_stopwords and len(w) >= 2]
    
    # Add ordinal/numeric keys (e.g., "2nd", "first", "second", "revised")
    ordinal_terms = {
        "1st", "first", "2nd", "second", "3rd", "third", "4th", "fourth", "5th", "fifth",
        "revised", "rev", "new", "updated", "enlarged", "expanded", "abridged", "complete"
    }
    
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

    def __init__(self):
        self.title_index: Dict[str, Set[int]] = defaultdict(set)
        self.author_index: Dict[str, Set[int]] = defaultdict(set)
        self.publisher_index: Dict[str, Set[int]] = defaultdict(set)
        self.edition_index: Dict[str, Set[int]] = defaultdict(set)
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
            author_keys = generate_author_keys(pub.author)
            for key in author_keys:
                self.author_index[key].add(pub_id)

        # Index by publisher
        if pub.publisher:
            publisher_keys = generate_publisher_keys(pub.publisher)
            for key in publisher_keys:
                self.publisher_index[key].add(pub_id)

        # Index by edition (gracefully handle missing edition data)
        if pub.edition:
            edition_keys = generate_edition_keys(pub.edition)
            for key in edition_keys:
                self.edition_index[key].add(pub_id)

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
            author_keys = generate_author_keys(query_pub.author)
            for key in author_keys:
                author_candidates.update(self.author_index.get(key, set()))

        # Find candidates by publisher (if available)
        publisher_candidates = set()
        if query_pub.publisher:
            publisher_keys = generate_publisher_keys(query_pub.publisher)
            for key in publisher_keys:
                publisher_candidates.update(self.publisher_index.get(key, set()))

        # Find candidates by edition (if available)
        edition_candidates = set()
        if query_pub.edition:
            edition_keys = generate_edition_keys(query_pub.edition)
            for key in edition_keys:
                edition_candidates.update(self.edition_index.get(key, set()))

        # Find candidates by year (within tolerance)
        year_candidates = set()
        if query_pub.year:
            for year_offset in range(-year_tolerance, year_tolerance + 1):
                target_year = query_pub.year + year_offset
                year_candidates.update(self.year_index.get(target_year, set()))

        # Combine candidates with priority, including edition when available
        if title_candidates:
            candidates.update(title_candidates)

            # If we have both title and author candidates, prefer intersection
            if author_candidates:
                intersection = title_candidates & author_candidates
                if intersection:
                    candidates = intersection
                    # If we also have publisher candidates, try triple intersection
                    if publisher_candidates:
                        triple_intersection = intersection & publisher_candidates
                        if triple_intersection:
                            candidates = triple_intersection
                            # If we also have edition candidates, try quadruple intersection
                            if edition_candidates:
                                quad_intersection = candidates & edition_candidates
                                if quad_intersection:
                                    candidates = quad_intersection
                                else:
                                    # Add edition candidates to existing intersection
                                    candidates.update(edition_candidates)
                        else:
                            # Add publisher candidates to existing intersection
                            candidates.update(publisher_candidates)
                            # Also add edition candidates if available
                            if edition_candidates:
                                candidates.update(edition_candidates)
                    elif edition_candidates:
                        # Have title+author and edition but no publisher
                        triple_intersection = intersection & edition_candidates
                        if triple_intersection:
                            candidates = triple_intersection
                        else:
                            candidates.update(edition_candidates)
                else:
                    # No intersection, but add author candidates too
                    candidates.update(author_candidates)
                    # Also add publisher and edition candidates if available
                    if publisher_candidates:
                        candidates.update(publisher_candidates)
                    if edition_candidates:
                        candidates.update(edition_candidates)
            elif publisher_candidates:
                # Have title and publisher but no author
                intersection = title_candidates & publisher_candidates
                if intersection:
                    candidates = intersection
                    # Try to add edition if available
                    if edition_candidates:
                        triple_intersection = candidates & edition_candidates
                        if triple_intersection:
                            candidates = triple_intersection
                        else:
                            candidates.update(edition_candidates)
                else:
                    candidates.update(publisher_candidates)
                    # Add edition candidates if available
                    if edition_candidates:
                        candidates.update(edition_candidates)
            elif edition_candidates:
                # Have title and edition but no author or publisher
                intersection = title_candidates & edition_candidates
                if intersection:
                    candidates = intersection
                else:
                    candidates.update(edition_candidates)
        elif author_candidates:
            # No title candidates, use author candidates
            candidates.update(author_candidates)
            # Also add publisher and edition candidates if available
            if publisher_candidates:
                candidates.update(publisher_candidates)
            if edition_candidates:
                candidates.update(edition_candidates)
        elif publisher_candidates:
            # Only publisher candidates available
            candidates.update(publisher_candidates)
            # Add edition candidates if available
            if edition_candidates:
                candidates.update(edition_candidates)
        elif edition_candidates:
            # Only edition candidates available
            candidates.update(edition_candidates)

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
            "publisher_keys": len(self.publisher_index),
            "edition_keys": len(self.edition_index),
            "year_keys": len(self.year_index),
            "avg_title_keys_per_pub": len(self.title_index) / max(1, len(self.publications)),
            "avg_author_keys_per_pub": len(self.author_index) / max(1, len(self.publications)),
            "avg_publisher_keys_per_pub": len(self.publisher_index) / max(1, len(self.publications)),
            "avg_edition_keys_per_pub": len(self.edition_index) / max(1, len(self.publications)),
        }


def build_index(publications: List[Publication]) -> PublicationIndex:
    """Build a complete index from a list of publications"""
    index = PublicationIndex()
    for pub in publications:
        index.add_publication(pub)
    return index
