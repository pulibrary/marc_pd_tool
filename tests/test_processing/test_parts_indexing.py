"""Test indexing with part number and part name support"""

# Local imports
from marc_pd_tool.data.publication import Publication
from marc_pd_tool.processing.indexer import PublicationIndex


class TestPartsIndexing:
    """Test indexing functionality with part numbers and names"""

    def test_indexing_with_parts(self):
        """Test that publications with parts are indexed using full title"""
        index = PublicationIndex()

        # Create a publication with parts
        pub = Publication(
            title="Complete Works",
            part_number="2",
            part_name="Novels",
            author="Jane Doe",
            pub_date="1950",
        )

        pub_id = index.add_publication(pub)

        # Verify publication was added
        assert pub_id == 0
        assert index.size() == 1

        # Test that we can find it using parts in the title
        query_pub = Publication(title="Complete Works Part 2 Novels", author="Jane Doe")

        candidates = index.get_candidates_list(query_pub)
        assert len(candidates) == 1
        assert candidates[0].original_title == "Complete Works"

    def test_partial_matching_with_parts(self):
        """Test that parts improve matching even with partial queries"""
        index = PublicationIndex()

        # Add publications with different parts
        pub1 = Publication(
            title="Complete Works", part_number="1", part_name="Poetry", author="Jane Doe"
        )

        pub2 = Publication(
            title="Complete Works", part_number="2", part_name="Novels", author="Jane Doe"
        )

        index.add_publication(pub1)
        index.add_publication(pub2)

        # Search for specific part
        query_novels = Publication(title="Complete Works Novels")
        candidates_novels = index.get_candidates_list(query_novels)

        # Should find the novels part
        assert len(candidates_novels) >= 1
        found_novels = any(c.original_part_name == "Novels" for c in candidates_novels)
        assert found_novels

        # Search for the other part
        query_poetry = Publication(title="Complete Works Poetry")
        candidates_poetry = index.get_candidates_list(query_poetry)

        # Should find the poetry part
        assert len(candidates_poetry) >= 1
        found_poetry = any(c.original_part_name == "Poetry" for c in candidates_poetry)
        assert found_poetry

    def test_parts_dont_affect_non_part_titles(self):
        """Test that normal titles without parts still work correctly"""
        index = PublicationIndex()

        # Add both normal and part-based publications
        normal_pub = Publication(title="Simple Book", author="John Doe")

        part_pub = Publication(
            title="Complete Works", part_number="1", part_name="Essays", author="Jane Doe"
        )

        index.add_publication(normal_pub)
        index.add_publication(part_pub)

        # Search for normal book should work
        query_normal = Publication(title="Simple Book")
        candidates_normal = index.get_candidates_list(query_normal)

        assert len(candidates_normal) == 1
        assert candidates_normal[0].original_title == "Simple Book"

    def test_empty_parts_handled_correctly(self):
        """Test that empty parts don't break indexing"""
        index = PublicationIndex()

        pub = Publication(title="Book Title", part_number="", part_name="", author="Author Name")

        index.add_publication(pub)

        # Should be able to find by title
        query = Publication(title="Book Title")
        candidates = index.get_candidates_list(query)

        assert len(candidates) == 1
        assert candidates[0].original_title == "Book Title"
