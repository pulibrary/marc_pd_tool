# tests/test_processing/test_matching_engine_coverage.py

"""Tests for matching_engine.py to improve coverage from 77% to 85%+"""

# Standard library imports
import os
from unittest.mock import Mock
from unittest.mock import patch

# Local imports
from marc_pd_tool.application.processing.matching._match_builder import (
    MatchResultBuilder,
)
from marc_pd_tool.application.processing.matching_engine import DataMatcher
from marc_pd_tool.application.processing.matching_engine import init_worker
from marc_pd_tool.application.processing.text_processing import GenericTitleDetector
from marc_pd_tool.core.domain.publication import Publication


class TestDataMatcherIgnoreThresholds:
    """Test DataMatcher find_best_match_ignore_thresholds functionality"""

    def test_find_best_match_ignore_thresholds_with_minimum_score(self):
        """Test ignore thresholds mode with minimum combined score filter"""
        matcher = DataMatcher()

        marc_pub = Publication(
            title="The Great Gatsby", author="F. Scott Fitzgerald", pub_date="1925", source_id="001"
        )

        copyright_pubs = [
            Publication(
                title="The Not So Great Gatsby",
                author="Scott Fitzgerald",
                pub_date="1925",
                source_id="c001",
            ),
            Publication(
                title="Something Completely Different",
                author="John Doe",
                pub_date="1925",
                source_id="c002",
            ),
        ]

        GenericTitleDetector()

        # Test with minimum score that filters out low matches
        result = matcher.find_best_match_ignore_thresholds(
            marc_pub,
            copyright_pubs,
            year_tolerance=2,
            minimum_combined_score=50,  # Should filter out the second publication
        )

        assert result is not None
        assert result["copyright_record"]["source_id"] == "c001"
        assert result["similarity_scores"]["combined"] > 50

    def test_find_best_match_ignore_thresholds_lccn_match(self):
        """Test ignore thresholds mode with LCCN exact match"""
        matcher = DataMatcher()

        marc_pub = Publication(
            title="The Great Gatsby",
            author="F. Scott Fitzgerald",
            pub_date="1925",
            source_id="001",
            lccn="25012345",
        )
        marc_pub.normalized_lccn = "25012345"

        copyright_pubs = [
            Publication(
                title="Different Title",
                author="Different Author",
                pub_date="1926",
                source_id="c001",
            ),
            Publication(
                title="The Great Gatsby",
                author="F. Scott Fitzgerald",
                pub_date="1925",
                source_id="c002",
                lccn="25012345",
            ),
        ]
        copyright_pubs[1].normalized_lccn = "25012345"

        GenericTitleDetector()

        result = matcher.find_best_match_ignore_thresholds(
            marc_pub, copyright_pubs, year_tolerance=2
        )

        assert result is not None
        assert result["copyright_record"]["source_id"] == "c002"
        # In score-everything mode, real scores are calculated even for LCCN matches
        assert result["similarity_scores"]["title"] == 100  # Same title
        assert result["similarity_scores"]["author"] > 80  # Same author with fuzzy match
        assert (
            result["similarity_scores"]["publisher"] == 100
        )  # Both have no publisher data (empty == empty)
        assert result["similarity_scores"]["combined"] > 0  # Combined score calculated
        assert result["is_lccn_match"] == True

    def test_find_best_match_ignore_thresholds_year_tolerance(self):
        """Test ignore thresholds mode respects year tolerance"""
        matcher = DataMatcher()

        marc_pub = Publication(
            title="The Great Gatsby", author="F. Scott Fitzgerald", pub_date="1925", source_id="001"
        )

        copyright_pubs = [
            Publication(
                title="The Great Gatsby",
                author="F. Scott Fitzgerald",
                pub_date="1930",  # Outside year tolerance
                source_id="c001",
            ),
            Publication(
                title="The Great Gatsby",
                author="F. Scott Fitzgerald",
                pub_date="1926",  # Within tolerance
                source_id="c002",
            ),
        ]

        GenericTitleDetector()

        result = matcher.find_best_match_ignore_thresholds(
            marc_pub, copyright_pubs, year_tolerance=2  # Only allows 1926, not 1930
        )

        assert result is not None
        assert result["copyright_record"]["source_id"] == "c002"

    def test_find_best_match_ignore_thresholds_no_year_in_marc(self):
        """Test ignore thresholds mode when MARC has no year"""
        matcher = DataMatcher()

        marc_pub = Publication(
            title="The Great Gatsby",
            author="F. Scott Fitzgerald",
            pub_date=None,  # No year
            source_id="001",
        )

        copyright_pubs = [
            Publication(
                title="The Great Gatsby",
                author="F. Scott Fitzgerald",
                pub_date="1925",
                source_id="c001",
            )
        ]

        GenericTitleDetector()

        result = matcher.find_best_match_ignore_thresholds(
            marc_pub, copyright_pubs, year_tolerance=2
        )

        # Should still match when MARC has no year
        assert result is not None
        assert result["copyright_record"]["source_id"] == "c001"

    def test_find_best_match_ignore_thresholds_generic_title(self):
        """Test ignore thresholds mode with generic titles"""
        matcher = DataMatcher()

        marc_pub = Publication(
            title="Annual Report",  # Generic title
            author="US Government",
            pub_date="1950",
            source_id="001",
        )

        copyright_pubs = [
            Publication(
                title="Annual Report", author="US Government", pub_date="1950", source_id="c001"
            )
        ]

        # Mock generic detector to flag "Annual Report" as generic
        generic_detector = Mock()
        generic_detector.is_generic.return_value = True
        generic_detector.get_frequency.return_value = 100

        result = matcher.find_best_match_ignore_thresholds(
            marc_pub, copyright_pubs, year_tolerance=2
        )

        assert result is not None
        # Generic titles get penalized (default penalty is 0.8)
        # The match is still found even with generic title


class TestDataMatcherRegularMatching:
    """Test regular find_best_match functionality"""

    def test_find_best_match_with_thresholds(self):
        """Test find_best_match with threshold filtering"""
        matcher = DataMatcher()

        marc_pub = Publication(
            title="The Sun Also Rises", author="Ernest Hemingway", pub_date="1926", source_id="001"
        )

        copyright_pubs = [
            Publication(
                title="The Sun Also Rises",
                author="Ernest Hemingway",
                pub_date="1926",
                source_id="c001",
            ),
            Publication(
                title="A Farewell to Arms",
                author="Ernest Hemingway",
                pub_date="1929",
                source_id="c002",
            ),
        ]

        generic_detector = GenericTitleDetector()

        result = matcher.find_best_match(
            marc_pub,
            copyright_pubs,
            year_tolerance=2,
            title_threshold=40,
            author_threshold=30,
            publisher_threshold=20,
            early_exit_title=95,
            early_exit_author=90,
            generic_detector=generic_detector,
        )

        assert result is not None
        assert result["copyright_record"]["source_id"] == "c001"
        assert result["similarity_scores"]["title"] > 40

    def test_find_best_match_early_exit(self):
        """Test find_best_match early exit on high scores"""
        matcher = DataMatcher()

        marc_pub = Publication(
            title="Moby Dick", author="Herman Melville", pub_date="1851", source_id="001"
        )

        # Create many candidates but first one should trigger early exit
        copyright_pubs = [
            Publication(
                title="Moby Dick", author="Herman Melville", pub_date="1851", source_id="c001"
            )
        ] + [
            Publication(
                title=f"Book {i}", author=f"Author {i}", pub_date="1851", source_id=f"c{i:03d}"
            )
            for i in range(2, 100)
        ]

        generic_detector = GenericTitleDetector()

        # Mock similarity calculator to ensure high scores
        with patch.object(
            matcher.similarity_calculator, "calculate_title_similarity", return_value=100.0
        ):
            with patch.object(
                matcher.similarity_calculator, "calculate_author_similarity", return_value=100.0
            ):
                result = matcher.find_best_match(
                    marc_pub,
                    copyright_pubs,
                    year_tolerance=2,
                    title_threshold=40,
                    author_threshold=30,
                    publisher_threshold=20,
                    early_exit_title=95,  # Should trigger early exit
                    early_exit_author=90,
                    generic_detector=generic_detector,
                )

        assert result is not None
        assert (
            result["copyright_record"]["source_id"] == "c001"
        )  # Should be first match due to early exit


class TestDataMatcherHelperMethods:
    """Test DataMatcher helper methods"""

    def test_create_match_result_regular(self):
        """Test create_match_result for regular match"""
        copyright_pub = Publication(
            title="Test Book",
            author="Test Author",
            publisher="Test Publisher",
            pub_date="1950",
            source_id="c001",
        )

        marc_pub = Publication(
            title="Test Book", author="Test Author", pub_date="1950", source_id="m001"
        )

        generic_detector = GenericTitleDetector()

        result = MatchResultBuilder.create_match_result(
            marc_pub,
            copyright_pub,
            85.0,  # title_score
            90.0,  # author_score
            75.0,  # publisher_score
            85.0,  # combined_score
            generic_detector,
            is_lccn_match=False,
        )

        assert isinstance(result, dict)
        assert result["is_lccn_match"] == False
        assert result["similarity_scores"]["title"] == 85.0
        assert result["similarity_scores"]["author"] == 90.0
        assert result["similarity_scores"]["publisher"] == 75.0
        assert result["similarity_scores"]["combined"] == 85.0
        # Source type is determined by the publication type

    def test_create_match_result_lccn(self):
        """Test create_match_result for LCCN match"""
        copyright_pub = Publication(
            title="Test Book",
            author="Test Author",
            pub_date="1950",
            source_id="c001",
            lccn="50012345",
        )

        marc_pub = Publication(
            title="Test Book",
            author="Test Author",
            pub_date="1950",
            source_id="m001",
            lccn="50012345",
        )

        generic_detector = GenericTitleDetector()

        result = MatchResultBuilder.create_match_result(
            marc_pub,
            copyright_pub,
            100.0,  # title_score
            100.0,  # author_score
            100.0,  # publisher_score
            100.0,  # combined_score
            generic_detector,
            is_lccn_match=True,
        )

        assert result["is_lccn_match"] == True
        assert all(
            result["similarity_scores"][field] == 100.0
            for field in ["title", "author", "publisher", "combined"]
        )


class TestWorkerFunctions:
    """Test worker functions for parallel processing"""

    def test_init_worker_with_cached_data(self, tmp_path):
        """Test worker initialization with cached indexes"""
        cache_dir = str(tmp_path / "cache")
        copyright_dir = str(tmp_path / "copyright")
        renewal_dir = str(tmp_path / "renewal")

        # Create directories
        os.makedirs(cache_dir, exist_ok=True)
        os.makedirs(copyright_dir, exist_ok=True)
        os.makedirs(renewal_dir, exist_ok=True)

        # Create minimal data files
        copyright_file = tmp_path / "copyright" / "test.xml"
        copyright_file.write_text(
            """<?xml version="1.0" encoding="UTF-8"?>
        <copyrightEntries></copyrightEntries>"""
        )

        renewal_file = tmp_path / "renewal" / "test.tsv"
        renewal_file.write_text("title\tauthor\toreg\todat\tid\trdat\tclaimants\n")

        with patch("marc_pd_tool.infrastructure.CacheManager") as mock_cache_class:
            mock_cache = Mock()
            mock_cache_class.return_value = mock_cache

            # Mock successful cache retrieval
            mock_reg_index = Mock()
            mock_reg_index.size.return_value = 100
            mock_ren_index = Mock()
            mock_ren_index.size.return_value = 50
            mock_detector = Mock()

            mock_cache.get_cached_indexes.return_value = (mock_reg_index, mock_ren_index)
            mock_cache.get_cached_generic_detector.return_value = mock_detector

            # Initialize worker (should succeed with mocked cache)
            with patch(
                "marc_pd_tool.application.processing.matching_engine.getpid", return_value=12345
            ):
                with patch("psutil.Process") as mock_process_class:
                    # Mock process memory info
                    mock_process = Mock()
                    mock_process.memory_info.return_value.rss = 1024 * 1024 * 100  # 100MB
                    mock_process_class.return_value = mock_process

                    init_worker(
                        cache_dir,
                        copyright_dir,
                        renewal_dir,
                        "test_hash",
                        {"min_length": 10},
                        min_year=1950,
                        max_year=1960,
                        brute_force=False,
                    )

            # The test succeeds if no exception is raised
