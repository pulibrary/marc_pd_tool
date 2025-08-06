# tests/test_processing/test_indexer.py

"""Tests for word-based indexing system"""

# Standard library imports
from unittest import TestCase

# Local imports
from marc_pd_tool.data.publication import Publication
from marc_pd_tool.processing.indexer import DataIndexer
from marc_pd_tool.processing.indexer import build_wordbased_index
from marc_pd_tool.processing.indexer import generate_wordbased_author_keys
from marc_pd_tool.processing.indexer import generate_wordbased_publisher_keys
from marc_pd_tool.processing.indexer import generate_wordbased_title_keys


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
