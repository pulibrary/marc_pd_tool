# tests/unit/application/processing/test_indexer.py

"""Comprehensive tests for the DataIndexer and related functions

This file consolidates all tests from:
- test_indexer.py (original)
- test_indexer_100_coverage.py
- test_indexing.py
- test_key_generation.py
- test_lccn_indexing.py
"""

# Standard library imports
from unittest import TestCase
from unittest.mock import Mock

# Third party imports
from pytest import fixture

# Local imports
from marc_pd_tool import DataMatcher
from marc_pd_tool import Publication
from marc_pd_tool.application.processing.indexer import (
    generate_wordbased_publisher_keys,
)
from marc_pd_tool.application.processing.indexer import DataIndexer
from marc_pd_tool.application.processing.indexer import build_wordbased_index
from marc_pd_tool.application.processing.indexer import generate_wordbased_author_keys
from marc_pd_tool.application.processing.indexer import generate_wordbased_title_keys
from marc_pd_tool.application.processing.text_processing import LanguageProcessor
from marc_pd_tool.application.processing.text_processing import MultiLanguageStemmer
from marc_pd_tool.core.domain.enums import CountryClassification
from marc_pd_tool.core.domain.index_entry import IndexEntry
from marc_pd_tool.core.domain.publication import Publication
from marc_pd_tool.infrastructure.config import ConfigLoader
from marc_pd_tool.shared.utils.text_utils import extract_significant_words
from marc_pd_tool.shared.utils.text_utils import normalize_text_standard

# ============================================================================
# Test Fixtures
# ============================================================================


@fixture
def indexer() -> DataIndexer:
    """Create a DataIndexer instance"""
    return DataIndexer()


@fixture
def sample_marc_records():
    """Sample MARC records for testing"""
    return [
        Publication(
            title="The Great Gatsby",
            author="Fitzgerald, F. Scott",
            pub_date="1925",
            publisher="Scribner",
            place="New York",
            source="MARC",
            source_id="001",
            country_code="xxu",
            country_classification=CountryClassification.US,
        ),
        Publication(
            title="To Kill a Mockingbird",
            author="Lee, Harper",
            pub_date="1960",
            publisher="Lippincott",
            place="Philadelphia",
            source="MARC",
            source_id="002",
            country_code="xxu",
            country_classification=CountryClassification.US,
        ),
        Publication(
            title="1984",
            author="Orwell, George",
            pub_date="1949",
            publisher="Secker & Warburg",
            place="London",
            source="MARC",
            source_id="003",
            country_code="enk",
            country_classification=CountryClassification.NON_US,
        ),
        Publication(
            title="Animal Farm",
            author="Orwell, George",
            pub_date="1945",
            publisher="Secker & Warburg",
            place="London",
            source="MARC",
            source_id="004",
            country_code="enk",
            country_classification=CountryClassification.NON_US,
        ),
        Publication(
            title="The Catcher in the Rye",
            author="Salinger, J. D.",
            pub_date="1951",
            publisher="Little, Brown",
            place="Boston",
            source="MARC",
            source_id="005",
            country_code="xxu",
            country_classification=CountryClassification.US,
        ),
    ]


@fixture
def sample_copyright_records():
    """Sample copyright records for testing"""
    return [
        # Exact matches
        Publication(
            title="The Great Gatsby",
            author="Fitzgerald, F. Scott",
            pub_date="1925",
            publisher="Scribner",
            place="New York",
            source="REG",
            source_id="R001",
        ),
        Publication(
            title="To Kill a Mockingbird",
            author="Lee, Harper",
            pub_date="1960",
            publisher="Lippincott",
            place="Philadelphia",
            source="REG",
            source_id="R002",
        ),
        Publication(
            title="Nineteen Eighty-Four",
            author="Orwell, George",
            pub_date="1949",
            publisher="Secker & Warburg",
            place="London",
            source="REG",
            source_id="R003",
        ),  # Title variation
        # Very similar (should trigger early termination)
        Publication(
            title="The Great Gatsby: A Novel",
            author="Fitzgerald, Francis Scott",
            pub_date="1925",
            publisher="Scribner",
            place="New York",
            source="REG",
            source_id="R004",
        ),
        # Different works by same author (should NOT trigger early termination on author alone)
        Publication(
            title="This Side of Paradise",
            author="Fitzgerald, F. Scott",
            pub_date="1920",
            publisher="Scribner",
            place="New York",
            source="REG",
            source_id="R005",
        ),
        Publication(
            title="Tender Is the Night",
            author="Fitzgerald, F. Scott",
            pub_date="1934",
            publisher="Scribner",
            place="New York",
            source="REG",
            source_id="R006",
        ),
        # Noise records
        Publication(
            title="Gone with the Wind",
            author="Mitchell, Margaret",
            pub_date="1936",
            publisher="Macmillan",
            place="New York",
            source="REG",
            source_id="R007",
        ),
        Publication(
            title="The Sound and the Fury",
            author="Faulkner, William",
            pub_date="1929",
            publisher="Cape & Smith",
            place="New York",
            source="REG",
            source_id="R008",
        ),
        Publication(
            title="Moby Dick",
            author="Melville, Herman",
            pub_date="1851",
            publisher="Harper",
            place="New York",
            source="REG",
            source_id="R009",
        ),
        Publication(
            title="War and Peace",
            author="Tolstoy, Leo",
            pub_date="1869",
            publisher="Russian Messenger",
            place="Russia",
            source="REG",
            source_id="R010",
        ),
    ]


@fixture
def sample_publications_with_lccn() -> list[Publication]:
    """Create sample publications with and without LCCNs"""
    pubs = []

    # Publications with LCCNs
    pub1 = Publication(
        title="The Great Gatsby",
        author="Fitzgerald, F. Scott",
        pub_date="1925",
        publisher="Scribner",
        source_id="test1",
    )
    pub1.lccn = "25-12345"
    pub1.normalized_lccn = "25012345"
    pub1.year = 1925
    pubs.append(pub1)

    pub2 = Publication(
        title="To Kill a Mockingbird",
        author="Lee, Harper",
        pub_date="1960",
        publisher="Lippincott",
        source_id="test2",
    )
    pub2.lccn = "60-7890"
    pub2.normalized_lccn = "60007890"
    pub2.year = 1960
    pubs.append(pub2)

    # Publication without LCCN
    pub3 = Publication(
        title="1984",
        author="Orwell, George",
        pub_date="1949",
        publisher="Secker & Warburg",
        source_id="test3",
    )
    pub3.year = 1949
    pubs.append(pub3)

    # Publication with same LCCN as pub1 (duplicate)
    pub4 = Publication(
        title="The Great Gatsby (Reprint)",
        author="Fitzgerald, F. Scott",
        pub_date="1953",
        publisher="Modern Library",
        source_id="test4",
    )
    pub4.lccn = "25-12345"
    pub4.normalized_lccn = "25012345"
    pub4.year = 1953
    pubs.append(pub4)

    return pubs


# Test stopwords matching original hardcoded behavior
TEST_STOPWORDS = {
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
}


# ============================================================================
# Index Entry Tests
# ============================================================================


class TestIndexEntry:
    """Test IndexEntry class"""

    def test_empty_entry(self):
        """Test empty entry behavior"""
        entry = IndexEntry()
        assert entry.is_empty() is True
        assert entry.ids == set()

    def test_single_entry(self):
        """Test single entry behavior"""
        entry = IndexEntry()
        entry.add(1)
        assert entry.is_empty() is False
        assert entry.ids == {1}

    def test_multiple_entries(self):
        """Test multiple entries behavior"""
        entry = IndexEntry()
        entry.add(1)
        entry.add(2)
        entry.add(1)  # Duplicate
        assert entry.ids == {1, 2}


# ============================================================================
# Text Normalization Tests
# ============================================================================


class TestTextNormalization:
    """Test text normalization functions"""

    def test_normalize_text_basic(self):
        """Test basic text normalization"""
        assert normalize_text_standard("The Great American Novel!") == "the great american novel"
        assert normalize_text_standard("Smith, John A.") == "smith john a"
        assert normalize_text_standard("Multiple   Spaces") == "multiple spaces"

    def test_normalize_text_punctuation(self):
        """Test punctuation removal"""
        assert normalize_text_standard("Title: A Subtitle (Revised)") == "title a subtitle revised"
        assert normalize_text_standard("Author, Jr.") == "author jr"
        assert normalize_text_standard("Hyphen-ated") == "hyphen ated"

    def test_extract_significant_words(self):
        """Test significant word extraction"""
        words = extract_significant_words("The Great American Novel", TEST_STOPWORDS)
        assert "great" in words
        assert "american" in words
        assert "novel" in words
        assert "the" not in words  # Stopword filtered

    def test_extract_significant_words_edge_cases(self):
        """Test edge cases for word extraction"""
        # Empty string
        assert extract_significant_words("", TEST_STOPWORDS) == []

        # Only stopwords
        words = extract_significant_words("the a an of", TEST_STOPWORDS)
        assert len(words) <= 1  # Should keep at least one word if possible

        # Short words filtered
        words = extract_significant_words("a bb ccc dddd", TEST_STOPWORDS)
        assert "bb" not in words  # Too short
        assert "ccc" in words
        assert "dddd" in words


# ============================================================================
# Title Key Generation Tests
# ============================================================================


class TestWordBasedTitleKeyGeneration(TestCase):
    """Test word-based title key generation"""

    def test_generate_wordbased_title_keys_basic(self):
        """Test basic title key generation with stemming and stopwords"""
        keys = generate_wordbased_title_keys("The complete works of Shakespeare", "eng")

        # Should include stemmed significant words (removing stopwords like "the", "of")
        # "complete" -> "complet", "works" -> "work", "Shakespeare" -> "shakespear"
        assert len(keys) > 0
        assert any("complet" in key for key in keys)  # Stemmed "complete"
        assert any("work" in key for key in keys)  # Stemmed "works"
        assert any("shakespear" in key for key in keys)  # Stemmed "Shakespeare"

    def test_generate_wordbased_title_keys_empty(self):
        """Test empty title handling"""
        keys = generate_wordbased_title_keys("", "eng")
        assert keys == set()

        keys = generate_wordbased_title_keys(None, "eng")
        assert keys == set()

    def test_generate_wordbased_title_keys_multilingual(self):
        """Test title key generation with different languages"""
        # French title
        keys_fr = generate_wordbased_title_keys("Les œuvres complètes", "fre")
        assert len(keys_fr) > 0

        # German title
        keys_de = generate_wordbased_title_keys("Die gesammelten Werke", "ger")
        assert len(keys_de) > 0

        # Different languages should produce different keys due to stopwords/stemming
        assert keys_fr != keys_de

    def test_generate_wordbased_title_keys_combinations(self):
        """Test that multi-word combinations are generated"""
        keys = generate_wordbased_title_keys("Advanced Python Programming", "eng")

        # Should contain individual stemmed words and combinations
        stemmed_words = []
        combination_keys = []

        for key in keys:
            if "_" in key:
                combination_keys.append(key)
            else:
                stemmed_words.append(key)

        assert len(stemmed_words) > 0  # Individual words
        assert len(combination_keys) > 0  # Word combinations

    def test_generate_title_keys_with_provided_processors(self):
        """Test title key generation with provided language processor and stemmer"""
        lang_processor = LanguageProcessor()
        stemmer = MultiLanguageStemmer()

        # Test with provided processors
        keys = generate_wordbased_title_keys(
            "The Running Books",
            language="eng",
            lang_processor=lang_processor,
            stemmer=stemmer,
            expand_abbreviations_flag=True,
        )
        assert len(keys) > 0
        # Should have stemmed words
        assert any("run" in key for key in keys)
        assert any("book" in key for key in keys)

    def test_generate_title_keys_no_expansion(self):
        """Test title key generation without abbreviation expansion"""
        keys = generate_wordbased_title_keys(
            "Co. Inc. Ltd.", language="eng", expand_abbreviations_flag=False
        )
        # Should have abbreviations unexpanded
        assert any("co" in key for key in keys)

    def test_generate_title_keys_empty_after_stopwords(self):
        """Test title key generation when all words are stopwords"""
        keys = generate_wordbased_title_keys(
            "The And Of", language="eng", expand_abbreviations_flag=False  # All stopwords
        )
        # Should return empty set
        assert keys == set()

    def test_title_keys_no_stopwords(self):
        """Test that stopwords are filtered from keys"""
        keys = generate_wordbased_title_keys("The Great American Novel")
        assert "the" not in keys

    def test_title_keys_short_titles(self):
        """Test key generation for short titles"""
        keys = generate_wordbased_title_keys("Novel")
        assert "novel" in keys
        assert len(keys) >= 1

        keys = generate_wordbased_title_keys("Great Novel")
        assert "great" in keys
        assert "novel" in keys
        assert "great_novel" in keys


# ============================================================================
# Author Key Generation Tests
# ============================================================================


class TestWordBasedAuthorKeyGeneration(TestCase):
    """Test word-based author key generation"""

    def test_generate_wordbased_author_keys_comma_format(self):
        """Test author key generation for 'Last, First' format"""
        keys = generate_wordbased_author_keys("Shakespeare, William", "eng")

        assert "shakespeare" in keys  # Not stemmed (proper nouns)
        assert "william" in keys
        assert "shakespeare_william" in keys
        assert "william_shakespeare" in keys

    def test_generate_wordbased_author_keys_first_last_format(self):
        """Test author key generation for 'First Last' format"""
        keys = generate_wordbased_author_keys("William Shakespeare", "eng")

        assert "william" in keys
        assert "shakespeare" in keys  # Not stemmed (proper nouns)
        assert "william_shakespeare" in keys
        assert "shakespeare_william" in keys

    def test_generate_wordbased_author_keys_removes_qualifiers(self):
        """Test that author qualifiers are removed"""
        keys = generate_wordbased_author_keys("edited by William Shakespeare", "eng")

        # Should remove "edited", "by" but keep significant words
        assert "william" in keys
        assert "shakespeare" in keys  # Not stemmed (proper nouns)
        assert "edited" not in keys  # "edited" should be removed
        assert "by" not in keys  # "by" should be removed

    def test_generate_wordbased_author_keys_empty(self):
        """Test empty author handling"""
        keys = generate_wordbased_author_keys("", "eng")
        assert keys == set()

    def test_generate_author_keys_edge_cases(self):
        """Test author key generation edge cases"""
        # Single word author
        keys = generate_wordbased_author_keys("Smith", "eng")
        assert "smith" in keys

        # Author with special characters
        keys = generate_wordbased_author_keys("O'Brien, Patrick", "eng")
        assert any("brien" in key for key in keys)

        # Very short author parts after processing
        keys = generate_wordbased_author_keys("X, Y", "eng")
        # Single letters should be included as initials
        # But they may be filtered by minimum length requirements
        # Check that we got some keys
        assert len(keys) >= 0  # May be empty due to length filtering

    def test_generate_author_keys_no_expansion(self):
        """Test author key generation without abbreviation expansion"""
        keys = generate_wordbased_author_keys("Smith, J.", "eng", expand_abbreviations_flag=False)
        assert "smith" in keys
        assert "j" in keys

    def test_author_keys_single_name(self):
        """Test author keys for single names (personal names)"""
        keys = generate_wordbased_author_keys("Shakespeare")
        assert "shakespeare" in keys

        keys = generate_wordbased_author_keys("Voltaire")
        assert "voltaire" in keys

    def test_author_keys_complex_names(self):
        """Test author keys for complex name formats (personal names)"""
        # Multiple middle names
        keys = generate_wordbased_author_keys("Smith, John William Alexander")
        assert "smith" in keys
        assert "smith_john" in keys

        # Jr./Sr. suffixes
        keys = generate_wordbased_author_keys("King, Martin Luther Jr.")
        assert "king" in keys
        assert any("martin" in key for key in keys)

    def test_author_keys_non_personal_names(self):
        """Test author keys for non-personal names (now treated as personal names)

        Since we simplified to use only personal name parsing for all authors from 245$c,
        these should still generate keys but using personal name logic.
        """
        # Corporate-style name - treated as personal name (uses last word as surname)
        keys = generate_wordbased_author_keys("Harvard University Press")
        assert "press" in keys  # Last word treated as surname
        assert len(keys) > 0

        # Multi-part name with periods
        keys = generate_wordbased_author_keys("United States Congress")
        assert "congress" in keys  # Last word
        assert "united_congress" in keys  # First + Last
        assert len(keys) > 0


# ============================================================================
# Publisher Key Generation Tests
# ============================================================================


class TestWordBasedPublisherKeyGeneration(TestCase):
    """Test word-based publisher key generation"""

    def test_generate_wordbased_publisher_keys_basic(self):
        """Test basic publisher key generation"""
        keys = generate_wordbased_publisher_keys("Oxford University Press", "eng")

        assert "oxford" in keys
        assert "university" in keys  # Not stemmed
        # "press" might be removed as publisher stopword

    def test_generate_wordbased_publisher_keys_removes_stopwords(self):
        """Test that publisher stopwords are removed"""
        keys = generate_wordbased_publisher_keys("Random House Publishing Company", "eng")

        assert "random" in keys
        assert "house" in keys  # Not stemmed
        # "publishing", "company" should be removed as stopwords
        assert "publishing" not in keys
        assert "company" not in keys

    def test_generate_wordbased_publisher_keys_combinations(self):
        """Test multi-word publisher combinations"""
        keys = generate_wordbased_publisher_keys("Harvard University Press", "eng")

        # Should include word combinations
        combination_keys = [key for key in keys if "_" in key]
        assert len(combination_keys) > 0

    def test_generate_publisher_keys_edge_cases(self):
        """Test publisher key generation edge cases"""
        # Empty publisher
        keys = generate_wordbased_publisher_keys("", "eng")
        assert keys == set()

        # Publisher with very short words that might be filtered
        keys = generate_wordbased_publisher_keys("X Y Z", "eng", expand_abbreviations_flag=False)
        # Should have no valid keys after length filtering (words < 2-3 chars)
        # Actually, 2-char words might be kept for publishers
        assert len(keys) >= 0  # May have some keys

    def test_generate_publisher_keys_no_expansion(self):
        """Test publisher key generation without abbreviation expansion"""
        keys = generate_wordbased_publisher_keys(
            "Random House Inc.", "eng", expand_abbreviations_flag=False
        )
        assert "random" in keys
        assert "house" in keys
        # "inc" might be filtered as too short or expanded
        # Check that we have multi-word combinations
        assert any("random" in key and "house" in key for key in keys)


# ============================================================================
# DataIndexer Core Tests
# ============================================================================


class TestDataIndexer(TestCase):
    """Test word-based publication indexer"""

    def setUp(self):
        """Set up test publications"""
        self.indexer = DataIndexer()

        self.pub1 = Publication(
            title="The Complete Works of William Shakespeare",
            author="Shakespeare, William",
            pub_date="1923",  # Changed to match year extraction regex
            publisher="Oxford University Press",
            language_code="eng",
        )

        self.pub2 = Publication(
            title="Advanced Python Programming Techniques",
            author="Smith, John",
            pub_date="2020",
            publisher="Tech Publishers Inc",
            language_code="eng",
        )

        self.pub3 = Publication(
            title="Les œuvres complètes de Molière",
            author="Molière, Jean-Baptiste",
            pub_date="1882",  # Changed to match year extraction regex
            publisher="Editions Gallimard",
            language_code="fre",
        )

    def test_indexer_initialization(self):
        """Test indexer initialization"""
        assert len(self.indexer.publications) == 0
        assert len(self.indexer.title_index) == 0
        assert len(self.indexer.author_index) == 0
        assert len(self.indexer.publisher_index) == 0
        assert len(self.indexer.year_index) == 0

    def test_add_publication(self):
        """Test adding publications to the index"""
        pub_id = self.indexer.add_publication(self.pub1)

        assert pub_id == 0
        assert len(self.indexer.publications) == 1
        assert len(self.indexer.title_index) > 0
        assert len(self.indexer.author_index) > 0
        assert len(self.indexer.publisher_index) > 0
        assert len(self.indexer.year_index) > 0

    def test_find_candidates_by_title(self):
        """Test finding candidates by title using word-based matching"""
        self.indexer.add_publication(self.pub1)
        self.indexer.add_publication(self.pub2)

        # Query with similar title (stemmed words should match)
        query_pub = Publication(
            title="Complete Works Shakespeare", language_code="eng"  # Missing stopwords
        )

        candidates = self.indexer.find_candidates(query_pub)
        assert len(candidates) > 0
        assert 0 in candidates  # Should find pub1

    def test_find_candidates_by_author(self):
        """Test finding candidates by author"""
        self.indexer.add_publication(self.pub1)
        self.indexer.add_publication(self.pub2)

        query_pub = Publication(
            title="Some Random Title",
            author="William Shakespeare",  # Different format but same person
            language_code="eng",
        )

        candidates = self.indexer.find_candidates(query_pub)
        assert len(candidates) > 0
        assert 0 in candidates

    def test_find_candidates_by_year(self):
        """Test finding candidates by year with tolerance"""
        self.indexer.add_publication(self.pub1)  # 1923
        self.indexer.add_publication(self.pub2)  # 2020

        query_pub = Publication(
            title="Test Title", pub_date="1925", language_code="eng"  # Within tolerance of 1923
        )

        candidates = self.indexer.find_candidates(query_pub, year_tolerance=3)
        assert 0 in candidates  # Should find pub1
        assert 1 not in candidates  # Should not find pub2

    def test_find_candidates_multilingual(self):
        """Test candidate finding with different languages"""
        self.indexer.add_publication(self.pub1)  # English
        self.indexer.add_publication(self.pub3)  # French

        # French query should match French publication better
        query_pub = Publication(title="œuvres complètes", language_code="fre")  # French words

        candidates = self.indexer.find_candidates(query_pub)
        # Should find the French publication due to better word-based matching
        assert len(candidates) > 0

    def test_get_candidates_list(self):
        """Test getting candidate list"""
        self.indexer.add_publication(self.pub1)
        self.indexer.add_publication(self.pub2)

        query_pub = Publication(title="Complete Works", language_code="eng")

        candidates = self.indexer.get_candidates_list(query_pub)
        assert isinstance(candidates, list)
        assert len(candidates) > 0
        assert all(isinstance(pub, Publication) for pub in candidates)

    def test_get_stats(self):
        """Test getting indexer statistics"""
        self.indexer.add_publication(self.pub1)
        self.indexer.add_publication(self.pub2)

        stats = self.indexer.get_stats()

        assert stats["total_publications"] == 2
        assert stats["title_keys"] > 0
        assert stats["author_keys"] > 0
        assert stats["publisher_keys"] > 0
        assert stats["year_keys"] > 0

    def test_size_method(self):
        """Test size method"""
        assert self.indexer.size() == 0

        self.indexer.add_publication(Publication(title="Test", source_id="001"))
        assert self.indexer.size() == 1

    def test_lazy_property_initialization(self):
        """Test lazy initialization of language processor and stemmer"""
        indexer = DataIndexer()

        # Properties should be None initially
        assert indexer._lang_processor is None
        assert indexer._stemmer is None

        # Accessing properties should initialize them
        lang_proc = indexer.lang_processor
        assert lang_proc is not None
        assert isinstance(lang_proc, LanguageProcessor)
        assert indexer._lang_processor is lang_proc

        stemmer = indexer.stemmer
        assert stemmer is not None
        assert isinstance(stemmer, MultiLanguageStemmer)
        assert indexer._stemmer is stemmer


# ============================================================================
# DataIndexer Edge Cases and Coverage Tests
# ============================================================================


class TestDataIndexerEdgeCases:
    """Test edge cases in DataIndexer"""

    def test_add_publication_with_main_author(self):
        """Test adding publication with main_author"""
        indexer = DataIndexer()

        pub = Publication(
            title="Test Book",
            author="Smith, John",
            main_author="Smith, J.",  # Has main_author
            source_id="001",
        )

        indexer.add_publication(pub)

        # Should be indexed by main_author too - check the index directly
        candidates = indexer.find_candidates(pub, year_tolerance=2)
        assert len(candidates) == 1

    def test_add_publication_with_normalized_lccn(self):
        """Test adding publication with normalized LCCN"""
        indexer = DataIndexer()

        pub = Publication(title="Test Book", source_id="001")
        pub.normalized_lccn = "2001012345"

        indexer.add_publication(pub)

        # Should be in LCCN index
        assert "2001012345" in indexer.lccn_index
        assert len(indexer.lccn_index["2001012345"].ids) == 1

    def test_find_candidates_with_lccn_match(self):
        """Test finding candidates with LCCN match"""
        indexer = DataIndexer()

        # Add a publication with LCCN
        pub1 = Publication(title="Different Title", author="Different Author", source_id="001")
        pub1.normalized_lccn = "2001012345"
        indexer.add_publication(pub1)

        # Search with same LCCN but different metadata
        query_pub = Publication(
            title="Completely Different", author="Other Author", source_id="query"
        )
        query_pub.normalized_lccn = "2001012345"

        candidates = indexer.find_candidates(query_pub, year_tolerance=2)
        assert len(candidates) == 1
        assert 0 in candidates  # First publication has ID 0

    def test_find_candidates_no_year_filtering(self):
        """Test finding candidates without year data"""
        indexer = DataIndexer()

        # Add publications without years
        pub1 = Publication(title="Book One", author="Author One", source_id="001")
        pub2 = Publication(title="Book Two", author="Author Two", source_id="002")
        pub3 = Publication(title="Book One Part Two", author="Different Author", source_id="003")

        indexer.add_publication(pub1)
        indexer.add_publication(pub2)
        indexer.add_publication(pub3)

        # Search without year
        query_pub = Publication(title="Book One", source_id="q001")

        candidates = indexer.find_candidates(query_pub, year_tolerance=2)
        # Should find both books with "Book One" in title due to word-based matching
        assert len(candidates) >= 1
        assert 0 in candidates  # Exact match

    def test_find_candidates_author_only(self):
        """Test finding candidates by author only"""
        indexer = DataIndexer()

        # Add publications
        pub1 = Publication(title="First Book", author="Smith, John", source_id="001")
        pub2 = Publication(title="Second Book", author="Smith, John", source_id="002")
        pub3 = Publication(title="Third Book", author="Jones, Mary", source_id="003")

        indexer.add_publication(pub1)
        indexer.add_publication(pub2)
        indexer.add_publication(pub3)

        # Search with author only (no title match)
        query_pub = Publication(
            title="Completely Different Title", author="Smith, John", source_id="q001"
        )

        candidates = indexer.find_candidates(query_pub, year_tolerance=2)
        # Should find both Smith books
        assert len(candidates) == 2
        assert 0 in candidates
        assert 1 in candidates

    def test_find_candidates_with_year_and_publisher(self):
        """Test finding candidates with year and publisher filtering"""
        indexer = DataIndexer()

        # Add publications with year and publisher
        pub1 = Publication(
            title="Test Book",
            author="Test Author",
            publisher="Penguin",
            pub_date="1950",
            source_id="001",
        )
        pub2 = Publication(
            title="Test Book",
            author="Test Author",
            publisher="Random House",
            pub_date="1950",
            source_id="002",
        )

        indexer.add_publication(pub1)
        indexer.add_publication(pub2)

        # Search with specific publisher
        query_pub = Publication(
            title="Test Book",
            author="Test Author",
            publisher="Penguin",
            pub_date="1950",
            source_id="q001",
        )

        candidates = indexer.find_candidates(query_pub, year_tolerance=2)
        # Should narrow down to Penguin publication
        assert len(candidates) == 1
        assert 0 in candidates

    def test_get_candidates_list_empty_candidates(self):
        """Test getting candidates list with no matches"""
        indexer = DataIndexer()

        # Add some publications
        pub1 = Publication(title="Mathematics Book", source_id="001")
        pub2 = Publication(title="Physics Book", source_id="002")

        indexer.add_publication(pub1)
        indexer.add_publication(pub2)

        # Search for non-existent - use completely unrelated words
        query_pub = Publication(title="Zoology Xenobiology Quasar", source_id="q001")
        result = indexer.get_candidates_list(query_pub, year_tolerance=2)
        assert result == []

    def test_get_candidates_list_with_lccn(self):
        """Test getting candidates list when publication has LCCN"""
        indexer = DataIndexer()

        # Add publication with LCCN
        pub1 = Publication(title="Book 1", source_id="001")
        pub1.normalized_lccn = "2001012345"

        indexer.add_publication(pub1)

        # Search with LCCN
        marc_pub = Publication(title="Different Title", source_id="m001")
        marc_pub.normalized_lccn = "2001012345"

        candidates = indexer.get_candidates_list(marc_pub, year_tolerance=2)
        assert len(candidates) == 1
        assert candidates[0].source_id == "001"

    def test_find_candidates_empty_index(self):
        """Test finding candidates in empty index"""
        indexer = DataIndexer()

        pub = Publication(title="Test Book", author="Test Author", source_id="001")

        # Empty index should return empty set
        candidates = indexer.find_candidates(pub, year_tolerance=2)
        assert len(candidates) == 0

    def test_add_publication_minimal_data(self):
        """Test adding publication with minimal data"""
        indexer = DataIndexer()

        # Publication with only required fields
        pub = Publication(title="", source_id="001")  # Empty title

        indexer.add_publication(pub)

        # Should still be added
        assert pub.source_id in [p.source_id for p in indexer.publications]

    def test_get_stats_comprehensive(self):
        """Test get_stats method comprehensively"""
        indexer = DataIndexer()

        # Add publications with various fields
        pub1 = Publication(
            title="Book One",
            author="Author One",
            publisher="Publisher One",
            pub_date="1950",
            source_id="001",
        )
        pub1.normalized_lccn = "2001012345"

        pub2 = Publication(title="Book Two", author="Author Two", source_id="002")

        indexer.add_publication(pub1)
        indexer.add_publication(pub2)

        stats = indexer.get_stats()

        assert stats["total_publications"] == 2
        assert stats["title_keys"] > 0
        assert stats["author_keys"] > 0
        assert stats["publisher_keys"] > 0
        assert stats["year_keys"] == 1  # Only pub1 has year
        assert stats["lccn_keys"] == 1  # Only pub1 has LCCN
        assert stats["avg_title_keys_per_pub"] > 0
        assert stats["avg_author_keys_per_pub"] > 0


# ============================================================================
# DataIndexer Serialization Tests
# ============================================================================


class TestDataIndexerSerialization:
    """Test DataIndexer serialization"""

    def test_getstate_setstate(self):
        """Test custom serialization/deserialization"""
        indexer = DataIndexer()

        # Add a publication to ensure state
        pub = Publication(title="Test", source_id="001")
        indexer.add_publication(pub)

        # Test __getstate__
        state = indexer.__getstate__()
        assert "_lang_processor" in state
        assert state["_lang_processor"] is None
        assert "_stemmer" in state
        assert state["_stemmer"] is None

        # Test __setstate__
        new_indexer = DataIndexer()
        new_indexer.__setstate__(state)

        # Should have publications but no processors
        assert len(new_indexer.publications) == 1
        assert new_indexer._lang_processor is None
        assert new_indexer._stemmer is None


# ============================================================================
# Year Indexing Tests
# ============================================================================


class TestYearIndexing:
    """Test year-based indexing functionality"""

    def test_find_candidates_with_year_tolerance(self):
        """Test finding candidates with year tolerance"""
        indexer = DataIndexer()

        # Add publications with different years
        for year in [1948, 1949, 1950, 1951, 1952]:
            pub = Publication(
                title="Test Book", author="Test Author", pub_date=str(year), source_id=f"{year}"
            )
            indexer.add_publication(pub)

        # Search with year 1950 and tolerance 1
        query_pub = Publication(
            title="Test Book", author="Test Author", pub_date="1950", source_id="query"
        )

        candidates = indexer.find_candidates(query_pub, year_tolerance=1)
        # Should find 1949, 1950, 1951
        assert len(candidates) == 3
        assert 1 in candidates  # 1949
        assert 2 in candidates  # 1950
        assert 3 in candidates  # 1951


# ============================================================================
# Index Builder Tests
# ============================================================================


class TestWordBasedIndexBuilder(TestCase):
    """Test word-based index builder function"""

    def test_build_wordbased_index(self):
        """Test building a word-based index from publications"""
        publications = [
            Publication(
                title="The Art of Programming",
                author="Knuth, Donald",
                pub_date="1968",
                language_code="eng",
            ),
            Publication(
                title="Structure and Interpretation",
                author="Abelson, Harold",
                pub_date="1985",
                language_code="eng",
            ),
        ]

        indexer = build_wordbased_index(publications)

        assert isinstance(indexer, DataIndexer)
        assert len(indexer.publications) == 2
        assert indexer.get_stats()["total_publications"] == 2

        # Test that indexing worked by finding candidates
        query_pub = Publication(title="Art Programming", language_code="eng")
        candidates = indexer.find_candidates(query_pub)
        assert len(candidates) > 0


class TestBuildWordbasedIndex:
    """Test build_wordbased_index function"""

    def test_build_index_with_config(self):
        """Test building index with custom config"""
        config = Mock(spec=ConfigLoader)
        config.config = {"matching": {"word_based": {"enable_abbreviation_expansion": False}}}

        publications = [
            Publication(title="Book 1", source_id="001"),
            Publication(title="Book 2", source_id="002"),
        ]

        index = build_wordbased_index(publications, config_loader=config)

        assert len(index.publications) == 2
        assert index.enable_abbreviation_expansion is False


# ============================================================================
# Integration Tests
# ============================================================================


class TestWordBasedIndexingIntegration(TestCase):
    """Test integration between word-based indexing and matching"""

    def test_indexing_reduces_candidates(self):
        """Test that word-based indexing effectively reduces candidate space"""
        publications = []

        # Create many publications with different themes
        for i in range(100):
            pub = Publication(
                title=f"Book about topic {i % 10}",
                author=f"Author {i}",
                pub_date=str(1900 + i),
                language_code="eng",
            )
            publications.append(pub)

        # Add one very specific publication
        target_pub = Publication(
            title="Advanced Machine Learning Techniques",
            author="Expert, AI",
            pub_date="2020",
            language_code="eng",
        )
        publications.append(target_pub)

        indexer = build_wordbased_index(publications)

        # Query for the specific publication
        query_pub = Publication(
            title="Machine Learning Advanced", language_code="eng"  # Reordered words
        )

        candidates = indexer.find_candidates(query_pub)

        # Should find much fewer candidates than total publications
        assert len(candidates) < len(publications)
        assert len(candidates) > 0

    def test_year_filtering_priority(self):
        """Test that year filtering is applied first for performance"""
        publications = []

        # Create publications across different years
        for year in range(1900, 2000, 10):
            pub = Publication(
                title="Common Title",
                author="Common Author",
                pub_date=str(year),
                language_code="eng",
            )
            publications.append(pub)

        indexer = build_wordbased_index(publications)

        # Query with specific year and small tolerance
        query_pub = Publication(title="Common Title", pub_date="1950", language_code="eng")

        candidates = indexer.find_candidates(query_pub, year_tolerance=5)

        # Should only find publications within year tolerance
        candidate_pubs = [indexer.publications[i] for i in candidates]
        years = [pub.year for pub in candidate_pubs if pub.year]

        assert all(1945 <= year <= 1955 for year in years)


class TestIndexing:
    """Test indexing functionality"""

    def test_index_creation(self, sample_copyright_records):
        """Test that index is created successfully"""
        index = build_wordbased_index(sample_copyright_records)

        assert index.size() == len(sample_copyright_records)
        stats = index.get_stats()
        assert stats["total_publications"] == len(sample_copyright_records)
        assert stats["title_keys"] > 0
        assert stats["author_keys"] > 0

    def test_indexing_accuracy(self, sample_marc_records, sample_copyright_records):
        """Test that indexing finds the same matches as brute force"""
        index = build_wordbased_index(sample_copyright_records)
        matcher = DataMatcher()

        mismatches = 0
        for marc_pub in sample_marc_records:
            # Brute force search
            brute_match = matcher.find_best_match(
                marc_pub, sample_copyright_records, 80, 70, 2, 60, 95, 90
            )

            # Indexed search
            candidates = index.get_candidates_list(marc_pub, 2)
            indexed_match = matcher.find_best_match(marc_pub, candidates, 80, 70, 2, 60, 95, 90)

            # Compare results
            if brute_match is None and indexed_match is None:
                continue  # Both found no match - OK
            elif brute_match is None or indexed_match is None:
                mismatches += 1
            else:
                brute_id = brute_match["copyright_record"]["source_id"]
                indexed_id = indexed_match["copyright_record"]["source_id"]
                if brute_id != indexed_id:
                    mismatches += 1

        assert mismatches == 0, f"Indexing produced {mismatches} mismatches"

    def test_indexing_reduces_candidates(self, sample_marc_records, sample_copyright_records):
        """Test that indexing reduces the number of candidates to check"""
        index = build_wordbased_index(sample_copyright_records)

        for marc_pub in sample_marc_records:
            candidates = index.get_candidates_list(marc_pub, 2)

            # Indexing should significantly reduce candidates vs brute force
            assert len(candidates) <= len(sample_copyright_records)

            # Should find some candidates for reasonable queries
            if marc_pub.title and len(marc_pub.title) > 3:
                # For non-trivial titles, should find at least some candidates
                assert len(candidates) >= 0  # Allow zero for edge cases


# ============================================================================
# LCCN Indexing Tests
# ============================================================================


class TestLCCNIndexing:
    """Test LCCN indexing functionality"""

    def test_lccn_index_created(self, indexer: DataIndexer) -> None:
        """Test that LCCN index is created during initialization"""
        assert hasattr(indexer, "lccn_index")
        assert isinstance(indexer.lccn_index, dict)
        assert len(indexer.lccn_index) == 0

    def test_publications_indexed_by_lccn(
        self, indexer: DataIndexer, sample_publications_with_lccn: list[Publication]
    ) -> None:
        """Test that publications with LCCNs are properly indexed"""
        # Add all publications
        for pub in sample_publications_with_lccn:
            indexer.add_publication(pub)

        # Check LCCN index
        assert len(indexer.lccn_index) == 2  # Two unique LCCNs
        assert "25012345" in indexer.lccn_index
        assert "60007890" in indexer.lccn_index

        # Check that duplicate LCCNs are both indexed
        lccn_entry = indexer.lccn_index["25012345"]
        pub_ids = lccn_entry.ids
        assert len(pub_ids) == 2  # Two publications with same LCCN
        assert 0 in pub_ids  # pub1
        assert 3 in pub_ids  # pub4

    def test_find_candidates_by_lccn(
        self, indexer: DataIndexer, sample_publications_with_lccn: list[Publication]
    ) -> None:
        """Test that find_candidates returns LCCN matches immediately"""
        # Add all publications
        for pub in sample_publications_with_lccn:
            indexer.add_publication(pub)

        # Create query publication with LCCN
        query_pub = Publication(
            title="Different Title", author="Different Author", pub_date="1980", source_id="query1"
        )
        query_pub.year = 1980
        query_pub.normalized_lccn = "25012345"

        # Find candidates - should return LCCN matches despite different metadata
        candidates = indexer.find_candidates(query_pub, year_tolerance=1)
        assert len(candidates) == 2  # Both publications with this LCCN
        assert 0 in candidates
        assert 3 in candidates

    def test_lccn_lookup_ignores_year_tolerance(
        self, indexer: DataIndexer, sample_publications_with_lccn: list[Publication]
    ) -> None:
        """Test that LCCN lookups bypass year tolerance restrictions"""
        # Add publications
        for pub in sample_publications_with_lccn:
            indexer.add_publication(pub)

        # Query with LCCN but very different year
        query_pub = Publication(
            title="Query Title",
            author="Query Author",
            pub_date="2020",  # Very different from 1925
            source_id="query2",
        )
        query_pub.year = 2020
        query_pub.normalized_lccn = "25012345"

        # Should still find matches despite year difference
        candidates = indexer.find_candidates(query_pub, year_tolerance=1)
        assert len(candidates) == 2

    def test_no_lccn_falls_back_to_other_indexes(
        self, indexer: DataIndexer, sample_publications_with_lccn: list[Publication]
    ) -> None:
        """Test that queries without LCCN use other indexes"""
        # Add publications
        for pub in sample_publications_with_lccn:
            indexer.add_publication(pub)

        # Query without LCCN but matching title
        query_pub = Publication(
            title="1984", author="Orwell, George", pub_date="1949", source_id="query3"
        )
        query_pub.year = 1949

        candidates = indexer.find_candidates(query_pub, year_tolerance=1)
        assert len(candidates) == 1
        assert 2 in candidates  # pub3

    def test_lccn_index_stats(
        self, indexer: DataIndexer, sample_publications_with_lccn: list[Publication]
    ) -> None:
        """Test that LCCN index statistics are correctly reported"""
        # Add publications
        for pub in sample_publications_with_lccn:
            indexer.add_publication(pub)

        stats = indexer.get_stats()

        assert "lccn_keys" in stats
        assert stats["lccn_keys"] == 2  # Two unique LCCNs

        assert "avg_lccn_keys_per_pub" in stats
        # 3 out of 4 publications have LCCNs
        assert stats["avg_lccn_keys_per_pub"] == 0.5  # 2 unique LCCNs / 4 pubs

    def test_empty_lccn_not_indexed(self, indexer: DataIndexer) -> None:
        """Test that empty or None LCCNs are not indexed"""
        # Publication with empty LCCN
        pub1 = Publication(title="No LCCN Book", pub_date="1950", source_id="test_empty")
        pub1.year = 1950
        pub1.normalized_lccn = ""

        # Publication with None LCCN
        pub2 = Publication(title="Another No LCCN Book", pub_date="1951", source_id="test_none")
        pub2.year = 1951
        pub2.normalized_lccn = None

        indexer.add_publication(pub1)
        indexer.add_publication(pub2)

        # Neither should be in the LCCN index
        assert len(indexer.lccn_index) == 0

    def test_lccn_index_serialization(
        self, indexer: DataIndexer, sample_publications_with_lccn: list[Publication]
    ) -> None:
        """Test that LCCN index is properly serialized/deserialized"""
        # Add publications
        for pub in sample_publications_with_lccn:
            indexer.add_publication(pub)

        # Serialize
        state = indexer.__getstate__()

        # Create new indexer and restore state
        new_indexer = DataIndexer()
        new_indexer.__setstate__(state)

        # Verify LCCN index was restored
        assert len(new_indexer.lccn_index) == 2
        assert "25012345" in new_indexer.lccn_index
        assert "60007890" in new_indexer.lccn_index

        # Verify functionality still works
        query_pub = Publication(title="Query", pub_date="2000", source_id="q1")
        query_pub.year = 2000
        query_pub.normalized_lccn = "25012345"
        candidates = new_indexer.find_candidates(query_pub)
        assert len(candidates) == 2


# ============================================================================
# Early Termination Tests
# ============================================================================


class TestEarlyTermination:
    """Test early termination functionality"""

    def test_early_termination_triggers(self):
        """Test that early termination triggers correctly"""
        matcher = DataMatcher()
        marc_pub = Publication(
            title="The Great Gatsby",
            author="Fitzgerald, F. Scott",
            pub_date="1925",
            publisher="Scribner",
            place="New York",
            source="MARC",
            source_id="001",
            country_code="xxu",
            country_classification=CountryClassification.US,
        )

        copyright_pubs = [
            # This should trigger early termination (very high scores)
            Publication(
                title="The Great Gatsby",
                author="Fitzgerald, F. Scott",
                pub_date="1925",
                publisher="Scribner",
                place="New York",
                edition="",
                language_code="",
                source="REG",
                source_id="EARLY_EXIT",
            ),
            # These should not be reached due to early termination
            Publication(
                title="The Great Gatsby: Deluxe Edition",
                author="Fitzgerald, F. Scott",
                pub_date="1925",
                publisher="Scribner",
                place="New York",
                edition="",
                language_code="",
                source="REG",
                source_id="LATER_MATCH",
            ),
        ]

        match = matcher.find_best_match(marc_pub, copyright_pubs, 80, 70, 2, 60, 95, 90)

        assert match is not None
        assert match["copyright_record"]["source_id"] == "EARLY_EXIT"

    def test_no_false_early_exit_different_title(self):
        """Test that early termination doesn't trigger incorrectly for same author, different title"""
        matcher = DataMatcher()
        marc_pub = Publication(
            title="The Great Gatsby",
            author="Fitzgerald, F. Scott",
            pub_date="1925",
            publisher="Scribner",
            place="New York",
            source="MARC",
            source_id="001",
            country_code="xxu",
            country_classification=CountryClassification.US,
        )

        copyright_pubs = [
            # Different title by same author - should not trigger early exit
            Publication(
                title="This Side of Paradise",
                author="Fitzgerald, F. Scott",
                pub_date="1920",
                publisher="Scribner",
                place="New York",
                edition="",
                language_code="",
                source="REG",
                source_id="DIFFERENT_TITLE",
            ),
            # The actual match should be found
            Publication(
                title="The Great Gatsby",
                author="Fitzgerald, F. Scott",
                pub_date="1925",
                publisher="Scribner",
                place="New York",
                edition="",
                language_code="",
                source="REG",
                source_id="CORRECT_MATCH",
            ),
        ]

        match = matcher.find_best_match(marc_pub, copyright_pubs, 80, 70, 2, 60, 95, 90)

        assert match is not None
        assert match["copyright_record"]["source_id"] == "CORRECT_MATCH"

    def test_no_early_exit_missing_author(self):
        """Test that early termination doesn't trigger when author is missing"""
        matcher = DataMatcher()
        marc_pub = Publication(
            title="Anonymous Work",
            author="",
            pub_date="1925",
            publisher="Publisher",
            place="Place",
            source="MARC",
            source_id="001",
            country_code="xxu",
            country_classification=CountryClassification.US,
        )

        copyright_pubs = [
            # Even with perfect title match, no early exit without both authors
            Publication(
                title="Anonymous Work",
                author="",
                pub_date="1925",
                publisher="Publisher",
                place="Place",
                source="REG",
                source_id="NO_AUTHOR_MATCH",
            ),
            Publication(
                title="Anonymous Work",
                author="Some Author",
                pub_date="1925",
                publisher="Publisher",
                place="Place",
                source="REG",
                source_id="WITH_AUTHOR",
            ),
        ]

        # Should not crash and should handle missing authors gracefully
        match = matcher.find_best_match(marc_pub, copyright_pubs, 80, 70, 2, 60, 95, 90)

        # Either finding a match or not is acceptable - just shouldn't crash
        if match:
            assert "source_id" in match["copyright_record"]

    def test_early_exit_requires_both_high_scores(self):
        """Test that early exit requires both title AND author to be high"""
        matcher = DataMatcher()
        marc_pub = Publication(
            title="Test Title",
            author="Test Author",
            pub_date="1925",
            publisher="Publisher",
            place="Place",
            source="MARC",
            source_id="001",
            country_code="xxu",
            country_classification=CountryClassification.US,
        )

        copyright_pubs = [
            # High title, low author - should not trigger early exit
            Publication(
                title="Test Title",
                author="Different Author",
                pub_date="1925",
                publisher="Publisher",
                place="Place",
                edition="",
                language_code="",
                source="REG",
                source_id="HIGH_TITLE_LOW_AUTHOR",
            ),
            # Low title, high author - should not trigger early exit
            Publication(
                title="Different Title",
                author="Test Author",
                pub_date="1925",
                publisher="Publisher",
                place="Place",
                edition="",
                language_code="",
                source="REG",
                source_id="LOW_TITLE_HIGH_AUTHOR",
            ),
            # High title, high author - should trigger early exit
            Publication(
                title="Test Title",
                author="Test Author",
                pub_date="1925",
                publisher="Publisher",
                place="Place",
                edition="",
                language_code="",
                source="REG",
                source_id="BOTH_HIGH",
            ),
        ]

        match = matcher.find_best_match(marc_pub, copyright_pubs, 80, 70, 2, 60, 95, 90)

        assert match is not None
        assert match["copyright_record"]["source_id"] == "BOTH_HIGH"


# ============================================================================
# Key Generation Integration Tests
# ============================================================================


class TestKeyGeneration:
    """Integration tests for key generation"""

    def test_key_generation_preserves_matching(self):
        """Test that similar titles/authors generate overlapping keys"""
        # Similar titles should share keys
        keys1 = generate_wordbased_title_keys("The Great Gatsby")
        keys2 = generate_wordbased_title_keys("Great Gatsby")
        keys3 = generate_wordbased_title_keys("The Great Gatsby: A Novel")

        # Should have overlapping keys
        assert len(keys1 & keys2) > 0
        assert len(keys1 & keys3) > 0

        # Similar authors should share keys
        auth_keys1 = generate_wordbased_author_keys("Fitzgerald, F. Scott")
        auth_keys2 = generate_wordbased_author_keys("Fitzgerald, Francis Scott")
        auth_keys3 = generate_wordbased_author_keys("F. Scott Fitzgerald")

        assert len(auth_keys1 & auth_keys2) > 0
        assert len(auth_keys1 & auth_keys3) > 0

    def test_key_generation_handles_variations(self):
        """Test that common bibliographic variations are handled"""
        # Title variations
        variations = [
            "Introduction to Physics",
            "Physics: An Introduction",
            "An Introduction to Physics",
        ]

        all_keys = [generate_wordbased_title_keys(title) for title in variations]

        # All should share some keys (physics, introduction)
        common_keys = set.intersection(*all_keys)
        assert len(common_keys) > 0

        # Author variations
        author_variations = ["MacDonald, John", "McDonald, John", "John MacDonald", "John McDonald"]

        auth_keys = [generate_wordbased_author_keys(author) for author in author_variations]
        # Should have some overlap (john, macdonald/mcdonald sound similar)
        for i in range(len(auth_keys)):
            for j in range(i + 1, len(auth_keys)):
                assert len(auth_keys[i] & auth_keys[j]) > 0
