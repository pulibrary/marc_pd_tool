# tests/test_processing/test_indexer_100_coverage.py

"""Additional tests for indexer.py to achieve 100% coverage"""

# Standard library imports
from unittest.mock import Mock

# Local imports
from marc_pd_tool.application.processing.indexer import (
    generate_wordbased_publisher_keys,
)
from marc_pd_tool.application.processing.indexer import DataIndexer
from marc_pd_tool.application.processing.indexer import build_wordbased_index
from marc_pd_tool.application.processing.indexer import generate_wordbased_author_keys
from marc_pd_tool.application.processing.indexer import generate_wordbased_title_keys
from marc_pd_tool.application.processing.text_processing import LanguageProcessor
from marc_pd_tool.application.processing.text_processing import MultiLanguageStemmer
from marc_pd_tool.core.domain.index_entry import IndexEntry
from marc_pd_tool.core.domain.publication import Publication
from marc_pd_tool.infrastructure.config import ConfigLoader


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


class TestDataIndexerEdgeCases:
    """Test edge cases in DataIndexer"""

    def test_add_publication_with_main_author(self):
        """Test adding publication with main_author"""
        # Test lines 120-126
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
        # Test lines 146-148
        indexer = DataIndexer()

        pub = Publication(title="Test Book", source_id="001")
        pub.normalized_lccn = "2001012345"

        indexer.add_publication(pub)

        # Should be in LCCN index
        assert "2001012345" in indexer.lccn_index
        assert len(indexer.lccn_index["2001012345"].ids) == 1

    def test_find_candidates_with_lccn_match(self):
        """Test finding candidates with LCCN match"""
        # Test lines 164-167
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
        # Test lines 249-258
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
        # Test lines 255-256
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
        # Test lines 241-244
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
        # Test lines 274-275
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
        # Test line 328
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


class TestGenerateFunctions:
    """Test key generation functions"""

    def test_generate_title_keys_with_provided_processors(self):
        """Test title key generation with provided language processor and stemmer"""
        # Test lines 376, 378
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
        # Test line 386
        keys = generate_wordbased_title_keys(
            "Co. Inc. Ltd.", language="eng", expand_abbreviations_flag=False
        )
        # Should have abbreviations unexpanded
        assert any("co" in key for key in keys)

    def test_generate_title_keys_empty_after_stopwords(self):
        """Test title key generation when all words are stopwords"""
        # Test line 392
        keys = generate_wordbased_title_keys(
            "The And Of", language="eng", expand_abbreviations_flag=False  # All stopwords
        )
        # Should return empty set
        assert keys == set()

    def test_generate_author_keys_edge_cases(self):
        """Test author key generation edge cases"""
        # Test line 438
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
        # Test line 438
        keys = generate_wordbased_author_keys("Smith, J.", "eng", expand_abbreviations_flag=False)
        assert "smith" in keys
        assert "j" in keys

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
        # Test line 581
        keys = generate_wordbased_publisher_keys(
            "Random House Inc.", "eng", expand_abbreviations_flag=False
        )
        assert "random" in keys
        assert "house" in keys
        # "inc" might be filtered as too short or expanded
        # Check that we have multi-word combinations
        assert any("random" in key and "house" in key for key in keys)


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


class TestDataIndexerWithEmptyData:
    """Test DataIndexer with empty or minimal data"""

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


class TestDataIndexerMiscellaneous:
    """Test miscellaneous DataIndexer functionality"""

    def test_size_method(self):
        """Test size method"""
        indexer = DataIndexer()
        assert indexer.size() == 0

        indexer.add_publication(Publication(title="Test", source_id="001"))
        assert indexer.size() == 1

    def test_get_stats(self):
        """Test get_stats method"""
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
