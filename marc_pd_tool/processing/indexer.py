# marc_pd_tool/processing/indexer.py

"""Publication indexer for fast lookup using multiple indexing strategies"""

# Standard library imports
from re import sub
from typing import Optional  # Needed for forward references

# Local imports
from marc_pd_tool.data.publication import Publication
from marc_pd_tool.infrastructure.config_loader import ConfigLoader
from marc_pd_tool.infrastructure.config_loader import get_config
from marc_pd_tool.processing.text_processing import LanguageProcessor
from marc_pd_tool.processing.text_processing import MultiLanguageStemmer
from marc_pd_tool.processing.text_processing import expand_abbreviations
from marc_pd_tool.utils.mixins import ConfigurableMixin
from marc_pd_tool.utils.types import JSONDict


class CompactIndexEntry:
    """Memory-efficient container for index entries - stores single int or set"""

    __slots__ = ("_data",)

    def __init__(self) -> None:
        self._data: int | set[int] | None = None  # None, int, or set

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

    def get_ids(self) -> set[int]:
        """Get all publication IDs as a set"""
        if self._data is None:
            return set()
        elif isinstance(self._data, int):
            return {self._data}
        else:
            # self._data is guaranteed to be a set here by the type check
            assert isinstance(self._data, set)
            return self._data.copy()

    def is_empty(self) -> bool:
        """Check if entry is empty"""
        return self._data is None


class DataIndexer(ConfigurableMixin):
    """Indexes publications for fast lookup using titles, authors, publishers, years, and LCCNs"""

    def __init__(self, config_loader: Optional["ConfigLoader"] = None) -> None:
        """Initialize the publication indexer

        Args:
            config_loader: Optional configuration loader
        """
        self.config = self._init_config(config_loader)

        # Storage for publications and indexes
        self.publications: list[Publication] = []

        # Word-based indexes using stemmed/processed terms
        self.title_index: dict[str, CompactIndexEntry] = {}
        self.author_index: dict[str, CompactIndexEntry] = {}
        self.publisher_index: dict[str, CompactIndexEntry] = {}
        self.year_index: dict[int, CompactIndexEntry] = {}
        self.lccn_index: dict[str, CompactIndexEntry] = {}

        # Initialize language processing components (lazy initialization to avoid pickling issues)
        self._lang_processor: Optional[LanguageProcessor] = None
        self._stemmer: Optional[MultiLanguageStemmer] = None

        # Get abbreviation expansion setting from config
        config_dict = self.config.config
        self.enable_abbreviation_expansion = bool(
            self._get_config_value(
                config_dict, "matching.word_based.enable_abbreviation_expansion", True
            )
        )

    def add_publication(self, pub: Publication) -> int:
        """Add a publication to the word-based index and return its ID"""
        pub_id = len(self.publications)
        self.publications.append(pub)

        # Index by title using word-based processing with publication's language
        title_keys = generate_wordbased_title_keys(
            pub.title,
            pub.language_code,
            self.lang_processor,
            self.stemmer,
            self.enable_abbreviation_expansion,
        )
        for key in title_keys:
            if key not in self.title_index:
                self.title_index[key] = CompactIndexEntry()
            self.title_index[key].add(pub_id)

        # Index by author using word-based preprocessing
        if pub.author:
            author_keys = generate_wordbased_author_keys(
                pub.author, pub.language_code, self.enable_abbreviation_expansion
            )
            for key in author_keys:
                if key not in self.author_index:
                    self.author_index[key] = CompactIndexEntry()
                self.author_index[key].add(pub_id)

        # Index by main author as well
        if pub.main_author:
            main_author_keys = generate_wordbased_author_keys(
                pub.main_author, pub.language_code, self.enable_abbreviation_expansion
            )
            for key in main_author_keys:
                if key not in self.author_index:
                    self.author_index[key] = CompactIndexEntry()
                self.author_index[key].add(pub_id)

        # Index by publisher using word-based preprocessing
        if pub.publisher:
            publisher_keys = generate_wordbased_publisher_keys(
                pub.publisher, pub.language_code, self.enable_abbreviation_expansion
            )
            for key in publisher_keys:
                if key not in self.publisher_index:
                    self.publisher_index[key] = CompactIndexEntry()
                self.publisher_index[key].add(pub_id)

        # Index by year for temporal filtering
        if pub.year:
            if pub.year not in self.year_index:
                self.year_index[pub.year] = CompactIndexEntry()
            self.year_index[pub.year].add(pub_id)

        # Index by normalized LCCN for direct lookups
        if pub.normalized_lccn:
            if pub.normalized_lccn not in self.lccn_index:
                self.lccn_index[pub.normalized_lccn] = CompactIndexEntry()
            self.lccn_index[pub.normalized_lccn].add(pub_id)

        return pub_id

    def find_candidates(self, query_pub: Publication, year_tolerance: int = 1) -> set[int]:
        """Find candidate publication IDs using word-based indexing

        Args:
            query_pub: Publication to find candidates for
            year_tolerance: Maximum year difference for matching

        Returns:
            Set of candidate publication IDs
        """
        # Check LCCN index first for direct O(1) lookup
        if query_pub.normalized_lccn:
            entry = self.lccn_index.get(query_pub.normalized_lccn)
            if entry and not entry.is_empty():
                # Direct LCCN match found - return immediately for best performance
                return entry.get_ids()

        candidates = set()

        # Find candidates by title using word-based processing
        title_keys = generate_wordbased_title_keys(
            query_pub.title,
            query_pub.language_code,
            self.lang_processor,
            self.stemmer,
            self.enable_abbreviation_expansion,
        )
        title_candidates = set()
        for key in title_keys:
            entry = self.title_index.get(key)
            if entry and not entry.is_empty():
                title_candidates.update(entry.get_ids())

        # Find candidates by author using word-based preprocessing
        author_candidates = set()
        if query_pub.author:
            author_keys = generate_wordbased_author_keys(
                query_pub.author, query_pub.language_code, self.enable_abbreviation_expansion
            )
            for key in author_keys:
                entry = self.author_index.get(key)
                if entry and not entry.is_empty():
                    author_candidates.update(entry.get_ids())

        # Also search by main author
        if query_pub.main_author:
            main_author_keys = generate_wordbased_author_keys(
                query_pub.main_author, query_pub.language_code, self.enable_abbreviation_expansion
            )
            for key in main_author_keys:
                entry = self.author_index.get(key)
                if entry and not entry.is_empty():
                    author_candidates.update(entry.get_ids())

        # Find candidates by publisher using word-based preprocessing
        publisher_candidates = set()
        if query_pub.publisher:
            publisher_keys = generate_wordbased_publisher_keys(
                query_pub.publisher, query_pub.language_code, self.enable_abbreviation_expansion
            )
            for key in publisher_keys:
                entry = self.publisher_index.get(key)
                if entry and not entry.is_empty():
                    publisher_candidates.update(entry.get_ids())

        # Find candidates by year (within tolerance) - APPLY FIRST for performance
        year_candidates = set()
        if query_pub.year:
            for year_offset in range(-year_tolerance, year_tolerance + 1):
                target_year = query_pub.year + year_offset
                entry = self.year_index.get(target_year)
                if entry and not entry.is_empty():
                    year_candidates.update(entry.get_ids())

        # CRITICAL: Apply year filtering FIRST (most selective)
        if year_candidates:
            candidates = year_candidates.copy()

            # Intersect with title candidates (word-based)
            if title_candidates:
                candidates &= title_candidates

                # Further narrow with author candidates
                if candidates and author_candidates:
                    title_author_intersection = candidates & author_candidates
                    if title_author_intersection:
                        candidates = title_author_intersection

                        # Final narrowing with publisher candidates
                        if candidates and publisher_candidates:
                            publisher_intersection = candidates & publisher_candidates
                            if publisher_intersection:
                                candidates = publisher_intersection
            elif author_candidates:
                candidates &= author_candidates
            elif publisher_candidates:
                candidates &= publisher_candidates
        else:
            # No year filtering - use title as primary filter
            if title_candidates:
                candidates = title_candidates
                if author_candidates:
                    candidates &= author_candidates
            elif author_candidates:
                candidates = author_candidates
            else:
                candidates = set()  # No viable candidates

        return candidates

    def get_candidates_list(
        self, query_pub: Publication, year_tolerance: int = 1
    ) -> list[Publication]:
        """Get list of candidate publications for word-based matching

        Args:
            query_pub: Publication to find candidates for
            year_tolerance: Maximum year difference for matching

        Returns:
            List of candidate publications
        """
        candidate_ids = self.find_candidates(query_pub, year_tolerance)
        return [self.publications[pub_id] for pub_id in candidate_ids]

    def size(self) -> int:
        """Return number of publications in index"""
        return len(self.publications)

    @property
    def lang_processor(self) -> LanguageProcessor:
        """Lazy initialization of language processor to avoid pickling issues"""
        if self._lang_processor is None:
            self._lang_processor = LanguageProcessor()
        return self._lang_processor

    @property
    def stemmer(self) -> MultiLanguageStemmer:
        """Lazy initialization of stemmer to avoid pickling issues"""
        if self._stemmer is None:
            self._stemmer = MultiLanguageStemmer()
        return self._stemmer

    def get_stats(self) -> dict[str, int | float]:
        """Get indexing statistics

        Returns:
            Dictionary with indexing statistics
        """
        return {
            "total_publications": len(self.publications),
            "title_keys": len(self.title_index),
            "author_keys": len(self.author_index),
            "publisher_keys": len(self.publisher_index),
            "edition_keys": 0,  # Not used in word-based indexing
            "year_keys": len(self.year_index),
            "lccn_keys": len(self.lccn_index),
            "avg_title_keys_per_pub": len(self.title_index) / max(1, len(self.publications)),
            "avg_author_keys_per_pub": len(self.author_index) / max(1, len(self.publications)),
            "avg_publisher_keys_per_pub": (
                len(self.publisher_index) / max(1, len(self.publications))
            ),
            "avg_edition_keys_per_pub": 0.0,  # Not used in word-based indexing
            "avg_lccn_keys_per_pub": len(self.lccn_index) / max(1, len(self.publications)),
        }

    def __getstate__(self) -> JSONDict:
        """Custom serialization to exclude non-picklable objects"""
        state = self.__dict__.copy()
        # Remove the unpicklable language processing objects
        state["_lang_processor"] = None
        state["_stemmer"] = None
        return state

    def __setstate__(self, state: JSONDict) -> None:
        """Custom deserialization to restore object state"""
        self.__dict__.update(state)
        # These will be recreated lazily when needed


def build_wordbased_index(
    publications: list[Publication], config_loader: Optional["ConfigLoader"] = None
) -> DataIndexer:
    """Build an index from a list of publications for fast lookup

    Args:
        publications: List of publications to index
        config_loader: Optional configuration loader

    Returns:
        DataIndexer with all publications indexed
    """
    indexer = DataIndexer(config_loader)

    for pub in publications:
        indexer.add_publication(pub)

    return indexer


def generate_wordbased_title_keys(
    title: str,
    language: str = "eng",
    lang_processor: LanguageProcessor | None = None,
    stemmer: MultiLanguageStemmer | None = None,
    expand_abbreviations_flag: bool = True,
) -> set[str]:
    """Generate word-based indexing keys for a title using stemming and stopwords

    Args:
        title: The title string to process
        language: Language code for processing (eng, fre, ger, spa, ita)
        lang_processor: Language processor for stopword removal
        stemmer: Multi-language stemmer
        expand_abbreviations_flag: Whether to expand abbreviations

    Returns:
        Set of stemmed word-based indexing keys
    """
    if not title:
        return set()

    # Use default processors if not provided
    if lang_processor is None:
        lang_processor = LanguageProcessor()
    if stemmer is None:
        stemmer = MultiLanguageStemmer()

    keys = set()

    # Expand abbreviations if enabled
    if expand_abbreviations_flag:
        expanded_title = expand_abbreviations(title)
    else:
        expanded_title = title

    # Remove stopwords to get significant words
    significant_words = lang_processor.remove_stopwords(expanded_title, language)

    if not significant_words:
        return set()

    # Stem the significant words
    stemmed_words = stemmer.stem_words(significant_words, language)

    # Create indexing keys from stemmed words
    for word in stemmed_words:
        if len(word) >= 2:  # Index words with 2+ characters after stemming
            keys.add(word)

    # Multi-word combinations for better precision
    if len(stemmed_words) >= 2:
        # First two stemmed words
        keys.add("_".join(stemmed_words[:2]))
        # Last two stemmed words
        if len(stemmed_words) > 2:
            keys.add("_".join(stemmed_words[-2:]))
        # First three stemmed words
        if len(stemmed_words) >= 3:
            keys.add("_".join(stemmed_words[:3]))

    return keys


def generate_wordbased_author_keys(
    author: str, language: str = "eng", expand_abbreviations_flag: bool = True
) -> set[str]:
    """Generate word-based indexing keys for author names with enhanced preprocessing

    Args:
        author: The author name string
        language: Language code for processing
        expand_abbreviations_flag: Whether to expand abbreviations

    Returns:
        Set of preprocessed author indexing keys
    """
    if not author:
        return set()

    keys = set()

    # Expand abbreviations if enabled
    if expand_abbreviations_flag:
        expanded_author = expand_abbreviations(author)
    else:
        expanded_author = author

    # Get author processing config
    config = get_config()
    author_config = config.author_processing_config
    author_stopwords_raw = author_config["stopwords"]
    author_titles_raw = author_config["titles"]

    # Type narrowing
    author_stopwords = (
        set(author_stopwords_raw) if isinstance(author_stopwords_raw, list) else set()
    )
    author_titles = author_titles_raw if isinstance(author_titles_raw, list) else []

    # Build regex pattern for author titles if available
    if author_titles and isinstance(author_titles, list):
        # Escape special chars and join with |
        title_pattern = (
            r"\b(" + "|".join(str(t) for t in author_titles if isinstance(t, str)) + r")\b\.?"
        )
    else:
        # Fallback pattern
        title_pattern = r"\b(dr|prof|sir|lord|lady|mrs?|ms)\b\.?"

    # Enhanced punctuation and formatting cleanup
    cleaned = expanded_author.lower()
    # Remove dates in parentheses (e.g., "Smith, John (1923-1995)")
    cleaned = sub(r"\([^)]*\)", "", cleaned)
    # Remove titles and qualifiers
    cleaned = sub(title_pattern, "", cleaned)
    # Normalize punctuation
    cleaned = sub(r"[^\w\s,.-]", " ", cleaned)
    cleaned = sub(r"\s+", " ", cleaned).strip()

    # Enhanced format handling with proper stopword filtering
    if "," in cleaned:
        # Format: "Last, First Middle" or "Last, F. M."
        parts = [p.strip() for p in cleaned.split(",")]
        if len(parts) >= 2:
            # Extract and filter surname words
            surname_words = []
            for word in parts[0].split():
                word = word.strip(".,")
                if word not in author_stopwords and len(word) >= 2:
                    surname_words.append(word)

            # Extract and filter given name words (allow initials)
            given_words = []
            for word in parts[1].split():
                word = word.strip(".,")
                if word not in author_stopwords and len(word) >= 1:
                    given_words.append(word)

            # Add surname components
            for word in surname_words:
                keys.add(word)

            # Add given name components (including initials)
            for word in given_words:
                keys.add(word)
                # Also add expanded initial if it's a single letter
                if len(word) == 1 and word.isalpha():
                    keys.add(word + ".")  # Add with period for matching

            # Enhanced surname + given name combinations
            if surname_words and given_words:
                # Primary combinations
                keys.add(f"{surname_words[0]}_{given_words[0]}")
                keys.add(f"{given_words[0]}_{surname_words[0]}")

                # Additional combinations for multiple surnames or given names
                if len(surname_words) > 1:
                    keys.add(f"{surname_words[-1]}_{given_words[0]}")
                    keys.add(f"{given_words[0]}_{surname_words[-1]}")
                if len(given_words) > 1:
                    keys.add(f"{surname_words[0]}_{given_words[-1]}")
                    keys.add(f"{given_words[-1]}_{surname_words[0]}")
    else:
        # Format: "First Middle Last" or "F. M. Last" - filter all words
        words = [
            word.strip(".,")
            for word in cleaned.split()
            if word.strip(".,") not in author_stopwords and len(word.strip(".,")) >= 2
        ]

        if not words:
            return set()

        # Separate likely surnames (usually last 1-2 words)
        if len(words) >= 2:
            # Assume last word is surname, rest are given names
            given_words = words[:-1]
            surname_words = [words[-1]]

            # Handle compound surnames (two capitalized words at end)
            if len(words) >= 3 and all(len(w) > 2 for w in words[-2:]):
                given_words = words[:-2]
                surname_words = words[-2:]
        else:
            # Single word - treat as surname
            given_words = []
            surname_words = words

        # Add all significant words
        for word in words:
            keys.add(word)
            # Handle initials
            if len(word) == 1 and word.isalpha():
                keys.add(word + ".")

        # Create combinations
        if given_words and surname_words:
            keys.add(f"{given_words[0]}_{surname_words[0]}")
            keys.add(f"{surname_words[0]}_{given_words[0]}")
            if len(surname_words) > 1:
                keys.add(f"{given_words[0]}_{surname_words[-1]}")
                keys.add(f"{surname_words[-1]}_{given_words[0]}")

    return keys


def generate_wordbased_publisher_keys(
    publisher: str, language: str = "eng", expand_abbreviations_flag: bool = True
) -> set[str]:
    """Generate word-based indexing keys for publisher names with enhanced preprocessing

    Args:
        publisher: The publisher name string
        language: Language code for processing
        expand_abbreviations_flag: Whether to expand abbreviations

    Returns:
        Set of preprocessed publisher indexing keys
    """
    if not publisher:
        return set()

    keys = set()

    # Expand abbreviations if enabled
    if expand_abbreviations_flag:
        expanded_publisher = expand_abbreviations(publisher)
    else:
        expanded_publisher = publisher

    # Get publisher stopwords from config
    config = get_config()
    publisher_stopwords = config.publisher_stopwords

    # Enhanced punctuation and formatting cleanup
    cleaned = expanded_publisher.lower()
    # Remove location information in parentheses or brackets
    cleaned = sub(r"[(\[].*?[)\]]", "", cleaned)
    # Remove dates
    cleaned = sub(r"\b\d{4}\b", "", cleaned)
    # Normalize punctuation and multiple spaces
    cleaned = sub(r"[^\w\s&.-]", " ", cleaned)
    cleaned = sub(r"\s+", " ", cleaned).strip()

    # Enhanced word filtering with flexible length requirements
    words = []
    for word in cleaned.split():
        word = word.strip(".,&-")
        # Keep meaningful words: 3+ chars normally, but allow 2 chars for common publisher terms
        if word not in publisher_stopwords:
            if len(word) >= 3 or (len(word) == 2 and word.isalpha()):
                words.append(word)

    # Fallback: if all words filtered, keep the longest significant words
    if not words:
        all_words = [w.strip(".,&-") for w in cleaned.split() if len(w.strip(".,&-")) >= 2]
        words = sorted(all_words, key=len, reverse=True)[:3]

    if not words:
        return set()

    # Add individual words
    for word in words:
        keys.add(word)

    # Enhanced multi-word combinations with better selection
    if len(words) >= 2:
        # Primary combinations: first two and last two words
        keys.add("_".join(words[:2]))
        if len(words) > 2:
            keys.add("_".join(words[-2:]))

        # Three-word combinations for better precision
        if len(words) >= 3:
            keys.add("_".join(words[:3]))
            # Also try middle combinations for longer publisher names
            if len(words) >= 4:
                mid_start = len(words) // 2 - 1
                keys.add("_".join(words[mid_start : mid_start + 2]))

    return keys
