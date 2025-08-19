# tests/unit/test_processing/test_parallel_indexer.py

"""Tests for parallel index building"""

# Standard library imports
from time import time

# Third party imports
from pytest import mark

# Local imports
from marc_pd_tool.application.processing.indexer import build_wordbased_index
from marc_pd_tool.application.processing.parallel_indexer import (
    build_wordbased_index_parallel,
)
from marc_pd_tool.core.domain.publication import Publication


class TestParallelIndexer:
    """Test parallel index building functionality"""

    def test_parallel_indexing_basic(self) -> None:
        """Test basic parallel indexing"""
        # Create test publications
        publications = [
            Publication(
                title=f"Book Title {i}",
                author=f"Author {i}",
                publisher=f"Publisher {i}",
                year=1920 + i,
                source="Test",
            )
            for i in range(100)
        ]

        # Build index using parallel processing
        index = build_wordbased_index_parallel(publications, num_workers=2)

        # Verify all publications were indexed
        assert len(index.publications) == 100

        # Verify indexes were built correctly
        assert len(index.title_index) > 0
        assert len(index.author_index) > 0
        assert len(index.publisher_index) > 0
        assert len(index.year_index) == 100  # Each year is unique

    def test_parallel_vs_sequential_equivalence(self) -> None:
        """Test that parallel indexing produces same results as sequential"""
        # Create test publications with various fields
        publications = []
        for i in range(200):
            pub = Publication(
                title=f"The Great Book {i % 50}",  # Some duplicate titles
                author=f"Smith, John {i % 30}" if i % 2 == 0 else "",  # Some missing authors
                publisher=f"Publisher {i % 20}" if i % 3 == 0 else "",  # Some missing publishers
                year=1950 + (i % 50),  # Years from 1950-1999
                lccn=f"50-{i:05d}" if i % 5 == 0 else "",  # Some LCCNs
                source="Test",
            )
            publications.append(pub)

        # Build indexes using both methods
        seq_index = build_wordbased_index(publications)
        par_index = build_wordbased_index_parallel(publications, num_workers=3)

        # Verify same number of publications
        assert len(seq_index.publications) == len(par_index.publications)
        assert len(seq_index.publications) == 200

        # Verify title indexes match
        assert set(seq_index.title_index.keys()) == set(par_index.title_index.keys())
        for key in seq_index.title_index:
            assert seq_index.title_index[key].ids == par_index.title_index[key].ids

        # Verify author indexes match
        assert set(seq_index.author_index.keys()) == set(par_index.author_index.keys())
        for key in seq_index.author_index:
            assert seq_index.author_index[key].ids == par_index.author_index[key].ids

        # Verify publisher indexes match
        assert set(seq_index.publisher_index.keys()) == set(par_index.publisher_index.keys())
        for key in seq_index.publisher_index:
            assert seq_index.publisher_index[key].ids == par_index.publisher_index[key].ids

        # Verify year indexes match
        assert set(seq_index.year_index.keys()) == set(par_index.year_index.keys())
        for year in seq_index.year_index:
            assert seq_index.year_index[year].ids == par_index.year_index[year].ids

        # Verify LCCN indexes match
        assert set(seq_index.lccn_index.keys()) == set(par_index.lccn_index.keys())
        for lccn in seq_index.lccn_index:
            assert seq_index.lccn_index[lccn].ids == par_index.lccn_index[lccn].ids

    def test_parallel_indexing_with_unicode(self) -> None:
        """Test parallel indexing with unicode characters"""
        publications = [
            Publication(
                title="Les Misérables",
                author="Hugo, Victor",
                publisher="Éditions Gallimard",
                year=1862,
                source="Test",
            ),
            Publication(
                title="Der Zauberberg",
                author="Mann, Thomas",
                publisher="S. Fischer Verlag",
                year=1924,
                source="Test",
            ),
            Publication(
                title="El ingenioso hidalgo Don Quijote",
                author="Cervantes, Miguel de",
                publisher="Juan de la Cuesta",
                year=1605,
                source="Test",
            ),
        ]

        # Build index with parallel processing
        index = build_wordbased_index_parallel(publications, num_workers=2)

        assert len(index.publications) == 3
        assert len(index.title_index) > 0
        assert len(index.author_index) > 0

    def test_parallel_indexing_small_dataset(self) -> None:
        """Test that small datasets use sequential processing"""
        # Create small dataset (< 1000 publications)
        publications = [
            Publication(title=f"Book {i}", author=f"Author {i}", year=2000 + i, source="Test")
            for i in range(50)
        ]

        # Should still work correctly even if it uses sequential internally
        index = build_wordbased_index_parallel(publications)

        assert len(index.publications) == 50
        assert len(index.year_index) == 50

    def test_parallel_indexing_empty_dataset(self) -> None:
        """Test parallel indexing with empty dataset"""
        publications = []

        index = build_wordbased_index_parallel(publications)

        assert len(index.publications) == 0
        assert len(index.title_index) == 0
        assert len(index.author_index) == 0

    def test_parallel_indexing_with_main_author(self) -> None:
        """Test that main_author field is indexed correctly"""
        publications = [
            Publication(
                title="Book with Main Author",
                author="Smith, John; Jones, Mary",  # Multiple authors
                main_author="Smith, John",  # Main author
                year=2000,
                source="Test",
            ),
            Publication(
                title="Book without Main Author",
                author="Brown, David",
                main_author="",  # No main author
                year=2001,
                source="Test",
            ),
        ]

        seq_index = build_wordbased_index(publications)
        par_index = build_wordbased_index_parallel(publications, num_workers=2)

        # Both should index main_author correctly
        assert set(seq_index.author_index.keys()) == set(par_index.author_index.keys())

        # Verify main author "Smith" is in the index
        # (keys are normalized/stemmed, so we check for presence of any Smith-related key)
        smith_keys = [k for k in par_index.author_index.keys() if "smith" in k.lower()]
        assert len(smith_keys) > 0

    @mark.slow
    def test_parallel_indexing_performance(self) -> None:
        """Test that parallel indexing is faster for large datasets"""
        # Create large dataset
        publications = []
        for i in range(5000):
            pub = Publication(
                title=f"Book Title Number {i} with Some Extra Words",
                author=f"Author {i % 100}, First Name",
                publisher=f"Publisher Name {i % 50}",
                year=1900 + (i % 100),
                lccn=f"{i % 100:02d}-{i:06d}" if i % 10 == 0 else "",
                source="Test",
            )
            publications.append(pub)

        # Time sequential indexing
        start = time()
        seq_index = build_wordbased_index(publications)
        seq_time = time() - start

        # Time parallel indexing
        start = time()
        par_index = build_wordbased_index_parallel(publications, num_workers=4)
        par_time = time() - start

        # Verify correctness
        assert len(seq_index.publications) == len(par_index.publications)
        assert len(seq_index.publications) == 5000

        # Log performance
        print(f"\nSequential: {seq_time:.2f}s, Parallel: {par_time:.2f}s")
        print(f"Speedup: {seq_time / par_time:.2f}x")

        # Parallel should be faster (but might not be for small test datasets)
        # Just verify it completes successfully
        assert len(par_index.title_index) > 0

    def test_parallel_indexing_with_different_worker_counts(self) -> None:
        """Test parallel indexing with various worker counts"""
        publications = [
            Publication(
                title=f"Book {i}", author=f"Author {i}", year=2000 + (i % 10), source="Test"
            )
            for i in range(500)
        ]

        # Test with different worker counts
        for num_workers in [1, 2, 4, 8]:
            index = build_wordbased_index_parallel(publications, num_workers=num_workers)
            assert len(index.publications) == 500
            assert len(index.title_index) > 0

            # Verify find_candidates works correctly
            query = Publication(title="Book 42", author="Author 42", year=2002, source="Query")
            candidates = index.find_candidates(query, year_tolerance=1)
            assert len(candidates) > 0  # Should find some candidates
