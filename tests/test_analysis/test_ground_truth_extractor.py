# tests/test_analysis/test_ground_truth_extractor.py

"""Test ground truth extraction for LCCN-matched pairs"""

# Standard library imports

# Third party imports
import pytest

# Local imports
from marc_pd_tool.data.enums import MatchType
from marc_pd_tool.data.ground_truth import GroundTruthStats
from marc_pd_tool.data.publication import Publication
from marc_pd_tool.processing.ground_truth_extractor import GroundTruthExtractor


class TestGroundTruthStats:
    """Test the GroundTruthStats dataclass"""

    def test_stats_properties(self):
        """Test calculated properties of GroundTruthStats"""
        stats = GroundTruthStats(
            total_marc_records=1000,
            marc_with_lccn=500,
            total_copyright_records=2000,
            copyright_with_lccn=1500,
            total_renewal_records=1000,
            registration_matches=100,
            renewal_matches=50,
            unique_lccns_matched=120,
        )

        assert stats.total_matches == 150
        assert stats.marc_lccn_coverage == 50.0
        assert stats.copyright_lccn_coverage == 75.0

    def test_stats_zero_division_handling(self):
        """Test that stats handle zero totals gracefully"""
        stats = GroundTruthStats(
            total_marc_records=0,
            marc_with_lccn=0,
            total_copyright_records=0,
            copyright_with_lccn=0,
            total_renewal_records=0,
            registration_matches=0,
            renewal_matches=0,
            unique_lccns_matched=0,
        )

        assert stats.total_matches == 0
        assert stats.marc_lccn_coverage == 0.0
        assert stats.copyright_lccn_coverage == 0.0


class TestGroundTruthExtractor:
    """Test the GroundTruthExtractor class"""

    def test_build_lccn_index(self):
        """Test building LCCN index from publications"""
        extractor = GroundTruthExtractor()

        pubs = [
            Publication("Title 1", lccn="n78890351"),
            Publication("Title 2", lccn="n79123456"),
            Publication("Title 3", lccn="n78890351"),  # Duplicate LCCN
            Publication("Title 4"),  # No LCCN
        ]

        index = extractor._build_lccn_index(pubs)

        assert len(index) == 2
        assert "n78890351" in index
        assert "n79123456" in index
        assert len(index["n78890351"]) == 2
        assert len(index["n79123456"]) == 1

    def test_extract_ground_truth_pairs_basic(self):
        """Test basic ground truth extraction returns Publications with matches"""
        extractor = GroundTruthExtractor()

        # Create MARC records
        marc1 = Publication("Book 1", author="Author 1", lccn="n78890351")
        marc1.year = 1950
        marc2 = Publication("Book 2", author="Author 2", lccn="n79123456")
        marc2.year = 1960
        marc3 = Publication("Book 3", author="Author 3")  # No LCCN

        marc_batches = [[marc1, marc2, marc3]]

        # Create copyright records
        copyright1 = Publication("Book 1", author="Author 1", lccn="n78890351")
        copyright1.year = 1950
        copyright1.source_id = "REG1"
        copyright2 = Publication("Book X", author="Author X", lccn="n80999999")  # No match

        copyright_pubs = [copyright1, copyright2]

        # Create renewal records
        renewal1 = Publication("Book 2", author="Author 2", lccn="n79123456")
        renewal1.year = 1960
        renewal1.source_id = "REN1"

        renewal_pubs = [renewal1]

        # Extract ground truth
        matched_publications, stats = extractor.extract_ground_truth_pairs(
            marc_batches, copyright_pubs, renewal_pubs
        )

        # Check returned publications
        assert len(matched_publications) == 2  # Two MARC records with matches

        # Check that matches are attached
        book1 = next(p for p in matched_publications if p.lccn == "n78890351")
        assert book1.registration_match is not None
        assert book1.registration_match.match_type == MatchType.LCCN
        assert book1.registration_match.source_id == "REG1"

        book2 = next(p for p in matched_publications if p.lccn == "n79123456")
        assert book2.renewal_match is not None
        assert book2.renewal_match.match_type == MatchType.LCCN
        assert book2.renewal_match.source_id == "REN1"

        # Check statistics
        assert stats.total_marc_records == 3
        assert stats.marc_with_lccn == 2
        assert stats.registration_matches == 1
        assert stats.renewal_matches == 1
        assert stats.unique_lccns_matched == 2

    def test_extract_ground_truth_pairs_no_renewals(self):
        """Test extraction with no renewal data"""
        extractor = GroundTruthExtractor()

        marc = Publication("Book", lccn="n78890351")
        copyright = Publication("Book", lccn="n78890351")
        copyright.source_id = "REG1"

        marc_batches = [[marc]]
        copyright_pubs = [copyright]

        matched_publications, stats = extractor.extract_ground_truth_pairs(
            marc_batches, copyright_pubs
        )

        assert len(matched_publications) == 1
        assert matched_publications[0].registration_match is not None
        assert matched_publications[0].registration_match.source_id == "REG1"
        assert stats.registration_matches == 1
        assert stats.renewal_matches == 0

    def test_filter_by_year_range(self):
        """Test filtering ground truth pairs by year"""
        extractor = GroundTruthExtractor()

        # Create publications with different years
        pub1950 = Publication("Book 1950")
        pub1950.year = 1950
        pub1960 = Publication("Book 1960")
        pub1960.year = 1960
        pub1970 = Publication("Book 1970")
        pub1970.year = 1970
        pub_none = Publication("Book None")  # No year

        publications = [pub1950, pub1960, pub1970, pub_none]

        # Test min year filter
        filtered = extractor.filter_by_year_range(publications, min_year=1960)
        assert len(filtered) == 2
        assert all(p.year >= 1960 for p in filtered if p.year)

        # Test max year filter
        filtered = extractor.filter_by_year_range(publications, max_year=1960)
        assert len(filtered) == 2
        assert all(p.year <= 1960 for p in filtered if p.year)

        # Test both filters
        filtered = extractor.filter_by_year_range(publications, min_year=1955, max_year=1965)
        assert len(filtered) == 1
        assert filtered[0].year == 1960

        # Test no filters
        filtered = extractor.filter_by_year_range(publications)
        assert len(filtered) == 4

    def test_get_coverage_report(self):
        """Test coverage report generation"""
        extractor = GroundTruthExtractor()

        marc_batches = [
            [
                Publication("Book 1", lccn="n78890351"),
                Publication("Book 2", lccn="n79123456"),
                Publication("Book 3"),  # No LCCN
            ]
        ]

        copyright_pubs = [
            Publication("Copyright 1", lccn="n78890351"),
            Publication("Copyright 2"),  # No LCCN
        ]

        renewal_pubs = [Publication("Renewal 1", lccn="n79123456")]

        report = extractor.get_coverage_report(marc_batches, copyright_pubs, renewal_pubs)

        assert report["marc_total"] == 3
        assert report["marc_with_lccn"] == 2
        assert report["marc_lccn_percentage"] == pytest.approx(66.67, rel=0.01)
        assert report["copyright_total"] == 2
        assert report["copyright_with_lccn"] == 1
        assert report["copyright_lccn_percentage"] == 50.0
        assert report["renewal_total"] == 1
        assert report["renewal_with_lccn"] == 1
        assert report["renewal_lccn_percentage"] == 100.0
