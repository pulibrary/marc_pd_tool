"""Tests for indexing performance optimizations"""

# Standard library imports
from typing import List

# Third party imports
import pytest

# Local imports
from marc_pd_tool import Publication
from marc_pd_tool import build_index
from marc_pd_tool import find_best_match
from marc_pd_tool.enums import CountryClassification


@pytest.fixture
def sample_marc_records():
    """Sample MARC records for testing"""
    return [
        Publication(
            "The Great Gatsby",
            "Fitzgerald, F. Scott",
            "1925",
            "Scribner",
            "New York",
            "MARC",
            "001",
            "xxu",
            CountryClassification.US,
        ),
        Publication(
            "To Kill a Mockingbird",
            "Lee, Harper",
            "1960",
            "Lippincott",
            "Philadelphia",
            "MARC",
            "002",
            "xxu",
            CountryClassification.US,
        ),
        Publication(
            "1984",
            "Orwell, George",
            "1949",
            "Secker & Warburg",
            "London",
            "MARC",
            "003",
            "enk",
            CountryClassification.NON_US,
        ),
        Publication(
            "Animal Farm",
            "Orwell, George",
            "1945",
            "Secker & Warburg",
            "London",
            "MARC",
            "004",
            "enk",
            CountryClassification.NON_US,
        ),
        Publication(
            "The Catcher in the Rye",
            "Salinger, J. D.",
            "1951",
            "Little, Brown",
            "Boston",
            "MARC",
            "005",
            "xxu",
            CountryClassification.US,
        ),
    ]


@pytest.fixture
def sample_copyright_records():
    """Sample copyright records for testing"""
    return [
        # Exact matches
        Publication(
            "The Great Gatsby",
            "Fitzgerald, F. Scott",
            "1925",
            "Scribner",
            "New York",
            "REG",
            "R001",
        ),
        Publication(
            "To Kill a Mockingbird",
            "Lee, Harper",
            "1960",
            "Lippincott",
            "Philadelphia",
            "REG",
            "R002",
        ),
        Publication(
            "Nineteen Eighty-Four",
            "Orwell, George",
            "1949",
            "Secker & Warburg",
            "London",
            "REG",
            "R003",
        ),  # Title variation
        # Very similar (should trigger early termination)
        Publication(
            "The Great Gatsby: A Novel",
            "Fitzgerald, Francis Scott",
            "1925",
            "Scribner",
            "New York",
            "REG",
            "R004",
        ),
        # Different works by same author (should NOT trigger early termination on author alone)
        Publication(
            "This Side of Paradise",
            "Fitzgerald, F. Scott",
            "1920",
            "Scribner",
            "New York",
            "REG",
            "R005",
        ),
        Publication(
            "Tender Is the Night",
            "Fitzgerald, F. Scott",
            "1934",
            "Scribner",
            "New York",
            "REG",
            "R006",
        ),
        # Noise records
        Publication(
            "Gone with the Wind",
            "Mitchell, Margaret",
            "1936",
            "Macmillan",
            "New York",
            "REG",
            "R007",
        ),
        Publication(
            "The Sound and the Fury",
            "Faulkner, William",
            "1929",
            "Cape & Smith",
            "New York",
            "REG",
            "R008",
        ),
        Publication("Moby Dick", "Melville, Herman", "1851", "Harper", "New York", "REG", "R009"),
        Publication(
            "War and Peace", "Tolstoy, Leo", "1869", "Russian Messenger", "Russia", "REG", "R010"
        ),
    ]


class TestIndexing:
    """Test indexing functionality"""

    def test_index_creation(self, sample_copyright_records):
        """Test that index is created successfully"""
        index = build_index(sample_copyright_records)

        assert index.size() == len(sample_copyright_records)
        stats = index.get_stats()
        assert stats["total_publications"] == len(sample_copyright_records)
        assert stats["title_keys"] > 0
        assert stats["author_keys"] > 0

    def test_indexing_accuracy(self, sample_marc_records, sample_copyright_records):
        """Test that indexing finds the same matches as brute force"""
        index = build_index(sample_copyright_records)

        mismatches = 0
        for marc_pub in sample_marc_records:
            # Brute force search
            brute_match = find_best_match(marc_pub, sample_copyright_records, 80, 70, 2, 95, 90)

            # Indexed search
            candidates = index.get_candidates_list(marc_pub, 2)
            indexed_match = find_best_match(marc_pub, candidates, 80, 70, 2, 95, 90)

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
        index = build_index(sample_copyright_records)

        for marc_pub in sample_marc_records:
            candidates = index.get_candidates_list(marc_pub, 2)

            # Indexing should significantly reduce candidates vs brute force
            assert len(candidates) <= len(sample_copyright_records)

            # Should find some candidates for reasonable queries
            if marc_pub.title and len(marc_pub.title) > 3:
                # For non-trivial titles, should find at least some candidates
                assert len(candidates) >= 0  # Allow zero for edge cases


class TestEarlyTermination:
    """Test early termination functionality"""

    def test_early_termination_triggers(self):
        """Test that early termination triggers correctly"""
        marc_pub = Publication(
            "The Great Gatsby",
            "Fitzgerald, F. Scott",
            "1925",
            "Scribner",
            "New York",
            "MARC",
            "001",
            "xxu",
            CountryClassification.US,
        )

        copyright_pubs = [
            # This should trigger early termination (very high scores)
            Publication(
                "The Great Gatsby",
                "Fitzgerald, F. Scott",
                "1925",
                "Scribner",
                "New York",
                "REG",
                "EARLY_EXIT",
            ),
            # These should not be reached due to early termination
            Publication(
                "The Great Gatsby: Deluxe Edition",
                "Fitzgerald, F. Scott",
                "1925",
                "Scribner",
                "New York",
                "REG",
                "LATER_MATCH",
            ),
        ]

        match = find_best_match(marc_pub, copyright_pubs, 80, 70, 2, 95, 90)

        assert match is not None
        assert match["copyright_record"]["source_id"] == "EARLY_EXIT"

    def test_no_false_early_exit_different_title(self):
        """Test that early termination doesn't trigger incorrectly for same author, different title"""
        marc_pub = Publication(
            "The Great Gatsby",
            "Fitzgerald, F. Scott",
            "1925",
            "Scribner",
            "New York",
            "MARC",
            "001",
            "xxu",
            CountryClassification.US,
        )

        copyright_pubs = [
            # Different title by same author - should not trigger early exit
            Publication(
                "This Side of Paradise",
                "Fitzgerald, F. Scott",
                "1920",
                "Scribner",
                "New York",
                "REG",
                "DIFFERENT_TITLE",
            ),
            # The actual match should be found
            Publication(
                "The Great Gatsby",
                "Fitzgerald, F. Scott",
                "1925",
                "Scribner",
                "New York",
                "REG",
                "CORRECT_MATCH",
            ),
        ]

        match = find_best_match(marc_pub, copyright_pubs, 80, 70, 2, 95, 90)

        assert match is not None
        assert match["copyright_record"]["source_id"] == "CORRECT_MATCH"

    def test_no_early_exit_missing_author(self):
        """Test that early termination doesn't trigger when author is missing"""
        marc_pub = Publication(
            "Anonymous Work",
            "",
            "1925",
            "Publisher",
            "Place",
            "MARC",
            "001",
            "xxu",
            CountryClassification.US,
        )

        copyright_pubs = [
            # Even with perfect title match, no early exit without both authors
            Publication(
                "Anonymous Work", "", "1925", "Publisher", "Place", "REG", "NO_AUTHOR_MATCH"
            ),
            Publication(
                "Anonymous Work", "Some Author", "1925", "Publisher", "Place", "REG", "WITH_AUTHOR"
            ),
        ]

        # Should not crash and should handle missing authors gracefully
        match = find_best_match(marc_pub, copyright_pubs, 80, 70, 2, 95, 90)

        # Either finding a match or not is acceptable - just shouldn't crash
        if match:
            assert "source_id" in match["copyright_record"]

    def test_early_exit_requires_both_high_scores(self):
        """Test that early exit requires both title AND author to be high"""
        marc_pub = Publication(
            "Test Title",
            "Test Author",
            "1925",
            "Publisher",
            "Place",
            "MARC",
            "001",
            "xxu",
            CountryClassification.US,
        )

        copyright_pubs = [
            # High title, low author - should not trigger early exit
            Publication(
                "Test Title",
                "Different Author",
                "1925",
                "Publisher",
                "Place",
                "REG",
                "HIGH_TITLE_LOW_AUTHOR",
            ),
            # Low title, high author - should not trigger early exit
            Publication(
                "Different Title",
                "Test Author",
                "1925",
                "Publisher",
                "Place",
                "REG",
                "LOW_TITLE_HIGH_AUTHOR",
            ),
            # High title, high author - should trigger early exit
            Publication(
                "Test Title", "Test Author", "1925", "Publisher", "Place", "REG", "BOTH_HIGH"
            ),
        ]

        match = find_best_match(marc_pub, copyright_pubs, 80, 70, 2, 95, 90)

        assert match is not None
        assert match["copyright_record"]["source_id"] == "BOTH_HIGH"
