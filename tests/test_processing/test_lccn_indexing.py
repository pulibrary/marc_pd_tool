# tests/test_processing/test_lccn_indexing.py

"""Tests for LCCN indexing functionality in DataIndexer"""

# Third party imports
from pytest import fixture

# Local imports
from marc_pd_tool.application.processing.indexer import DataIndexer
from marc_pd_tool.core.domain.publication import Publication


@fixture
def indexer() -> DataIndexer:
    """Create a DataIndexer instance"""
    return DataIndexer()


@fixture
def sample_publications() -> list[Publication]:
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


class TestLCCNIndexing:
    """Test LCCN indexing functionality"""

    def test_lccn_index_created(self, indexer: DataIndexer) -> None:
        """Test that LCCN index is created during initialization"""
        assert hasattr(indexer, "lccn_index")
        assert isinstance(indexer.lccn_index, dict)
        assert len(indexer.lccn_index) == 0

    def test_publications_indexed_by_lccn(
        self, indexer: DataIndexer, sample_publications: list[Publication]
    ) -> None:
        """Test that publications with LCCNs are properly indexed"""
        # Add all publications
        for pub in sample_publications:
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
        self, indexer: DataIndexer, sample_publications: list[Publication]
    ) -> None:
        """Test that find_candidates returns LCCN matches immediately"""
        # Add all publications
        for pub in sample_publications:
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
        self, indexer: DataIndexer, sample_publications: list[Publication]
    ) -> None:
        """Test that LCCN lookups bypass year tolerance restrictions"""
        # Add publications
        for pub in sample_publications:
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
        self, indexer: DataIndexer, sample_publications: list[Publication]
    ) -> None:
        """Test that queries without LCCN use other indexes"""
        # Add publications
        for pub in sample_publications:
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
        self, indexer: DataIndexer, sample_publications: list[Publication]
    ) -> None:
        """Test that LCCN index statistics are correctly reported"""
        # Add publications
        for pub in sample_publications:
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
        self, indexer: DataIndexer, sample_publications: list[Publication]
    ) -> None:
        """Test that LCCN index is properly serialized/deserialized"""
        # Add publications
        for pub in sample_publications:
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
