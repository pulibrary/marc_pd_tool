# tests/test_processing/test_publisher_early_exit.py

"""Tests for publisher early exit functionality"""

# Standard library imports
from unittest.mock import patch

# Local imports
from marc_pd_tool.data.publication import Publication
from marc_pd_tool.processing.matching_engine import DataMatcher


class TestPublisherEarlyExit:
    """Test that publisher score is included in early exit decision"""

    def test_early_exit_with_all_high_scores(self):
        """Test early exit when title, author, and publisher all meet thresholds"""
        matcher = DataMatcher()

        marc_pub = Publication(
            title="The Great Gatsby",
            author="F. Scott Fitzgerald",
            publisher="Charles Scribner's Sons",
            pub_date="1925",
            source_id="001",
        )

        # Create many candidates to test early exit
        copyright_pubs = []

        # First publication should trigger early exit
        perfect_match = Publication(
            title="The Great Gatsby",
            author="F. Scott Fitzgerald",
            publisher="Charles Scribner's Sons",
            pub_date="1925",
            source_id="c001",
        )
        copyright_pubs.append(perfect_match)

        # Add many more that should not be evaluated due to early exit
        for i in range(2, 100):
            pub = Publication(
                title=f"Different Book {i}",
                author=f"Different Author {i}",
                publisher=f"Different Publisher {i}",
                pub_date="1925",
                source_id=f"c{i:03d}",
            )
            copyright_pubs.append(pub)

        # Mock the similarity calculator to track calls
        with patch.object(
            matcher.similarity_calculator, "calculate_title_similarity"
        ) as mock_title:
            with patch.object(
                matcher.similarity_calculator, "calculate_author_similarity"
            ) as mock_author:
                with patch.object(
                    matcher.similarity_calculator, "calculate_publisher_similarity"
                ) as mock_publisher:
                    # Set up return values for the first match
                    mock_title.return_value = 100.0
                    mock_author.return_value = 100.0
                    mock_publisher.return_value = 100.0

                    result = matcher.find_best_match(
                        marc_pub,
                        copyright_pubs,
                        title_threshold=40,
                        author_threshold=30,
                        year_tolerance=1,
                        publisher_threshold=30,
                        early_exit_title=95,
                        early_exit_author=90,
                        early_exit_publisher=85,
                        generic_detector=None,
                    )

                    assert result is not None
                    assert result["copyright_record"]["source_id"] == "c001"

                    # Should have only evaluated the first candidate due to early exit
                    assert mock_title.call_count == 1
                    assert mock_author.call_count == 1
                    assert mock_publisher.call_count == 1

    def test_no_early_exit_when_publisher_low(self):
        """Test no early exit when publisher score is below threshold"""
        matcher = DataMatcher()

        marc_pub = Publication(
            title="The Great Gatsby",
            author="F. Scott Fitzgerald",
            publisher="Charles Scribner's Sons",
            pub_date="1925",
            source_id="001",
        )

        copyright_pubs = [
            Publication(
                title="The Great Gatsby",
                author="F. Scott Fitzgerald",
                publisher="Different Publisher",  # Low publisher match
                pub_date="1925",
                source_id="c001",
            ),
            Publication(
                title="The Great Gatsby",
                author="F. Scott Fitzgerald",
                publisher="Charles Scribner's Sons",  # Perfect publisher match
                pub_date="1925",
                source_id="c002",
            ),
        ]

        # Mock the similarity calculator
        with patch.object(
            matcher.similarity_calculator, "calculate_title_similarity"
        ) as mock_title:
            with patch.object(
                matcher.similarity_calculator, "calculate_author_similarity"
            ) as mock_author:
                with patch.object(
                    matcher.similarity_calculator, "calculate_publisher_similarity"
                ) as mock_publisher:
                    mock_title.return_value = 100.0
                    mock_author.return_value = 100.0

                    # First call returns low score, second returns high score
                    mock_publisher.side_effect = [20.0, 100.0]

                    result = matcher.find_best_match(
                        marc_pub,
                        copyright_pubs,
                        title_threshold=40,
                        author_threshold=30,
                        year_tolerance=1,
                        publisher_threshold=30,
                        early_exit_title=95,
                        early_exit_author=90,
                        early_exit_publisher=85,  # High threshold
                        generic_detector=None,
                    )

                    assert result is not None
                    # Should have evaluated both candidates (no early exit on first)
                    assert mock_title.call_count == 2
                    assert mock_author.call_count == 2
                    assert mock_publisher.call_count == 2

                    # Should return the second match (better combined score)
                    assert result["copyright_record"]["source_id"] == "c002"

    def test_early_exit_without_publisher_data(self):
        """Test early exit still works when no publisher data exists"""
        matcher = DataMatcher()

        marc_pub = Publication(
            title="The Great Gatsby",
            author="F. Scott Fitzgerald",
            # No publisher data
            pub_date="1925",
            source_id="001",
        )

        copyright_pubs = [
            Publication(
                title="The Great Gatsby",
                author="F. Scott Fitzgerald",
                # No publisher data
                pub_date="1925",
                source_id="c001",
            ),
            Publication(
                title="Another Book", author="Another Author", pub_date="1925", source_id="c002"
            ),
        ]

        # Mock the similarity calculator
        with patch.object(
            matcher.similarity_calculator, "calculate_title_similarity"
        ) as mock_title:
            with patch.object(
                matcher.similarity_calculator, "calculate_author_similarity"
            ) as mock_author:
                with patch.object(
                    matcher.similarity_calculator, "calculate_publisher_similarity"
                ) as mock_publisher:
                    mock_title.side_effect = [100.0, 0.0]
                    mock_author.side_effect = [100.0, 0.0]
                    mock_publisher.return_value = 0.0  # No publisher data

                    result = matcher.find_best_match(
                        marc_pub,
                        copyright_pubs,
                        title_threshold=40,
                        author_threshold=30,
                        year_tolerance=1,
                        publisher_threshold=30,
                        early_exit_title=95,
                        early_exit_author=90,
                        early_exit_publisher=85,
                        generic_detector=None,
                    )

                    assert result is not None
                    assert result["copyright_record"]["source_id"] == "c001"

                    # Should have only evaluated first candidate (early exit)
                    # When no publisher data, publisher threshold is ignored
                    assert mock_title.call_count == 1
                    assert mock_author.call_count == 1
                    assert mock_publisher.call_count == 1

    def test_publisher_threshold_enforcement(self):
        """Test that publisher threshold is enforced when data exists"""
        matcher = DataMatcher()

        marc_pub = Publication(
            title="Test Book",
            author="Test Author",
            publisher="Test Publisher",
            pub_date="1950",
            source_id="001",
        )

        copyright_pubs = [
            Publication(
                title="Test Book",
                author="Test Author",
                publisher="Wrong Publisher",  # Should fail threshold
                pub_date="1950",
                source_id="c001",
            )
        ]

        result = matcher.find_best_match(
            marc_pub,
            copyright_pubs,
            title_threshold=40,
            author_threshold=30,
            year_tolerance=1,
            publisher_threshold=80,  # High threshold
            early_exit_title=95,
            early_exit_author=90,
            early_exit_publisher=85,
            generic_detector=None,
        )

        # Should not find a match due to publisher threshold
        assert result is None
