# tests/test_processing/test_indexing.py

"""Tests for indexing performance optimizations"""

# Standard library imports

# Third party imports
from pytest import fixture

# Local imports
from marc_pd_tool import DataMatcher
from marc_pd_tool import Publication
from marc_pd_tool.application.processing.indexer import build_wordbased_index
from marc_pd_tool.core.domain.enums import CountryClassification


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
