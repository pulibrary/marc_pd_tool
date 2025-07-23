# tests/test_analysis/test_ground_truth_extractor.py

"""Test ground truth extraction for LCCN-matched pairs"""

# Standard library imports
from pathlib import Path
import sys

# Third party imports
import pytest

# Add scripts directory to path for analysis module imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
# Third party imports
from analysis.ground_truth_extractor import GroundTruthExtractor
from analysis.ground_truth_extractor import GroundTruthPair
from analysis.ground_truth_extractor import GroundTruthStats

# Local imports
from marc_pd_tool.data.publication import Publication


class TestGroundTruthPair:
    """Test the GroundTruthPair dataclass"""

    def test_valid_pair_creation(self):
        """Test creating a valid ground truth pair"""
        marc_pub = Publication("Test Title", lccn="n78-890351", source="MARC")
        copyright_pub = Publication("Test Title", lccn="n78890351", source="Copyright")

        pair = GroundTruthPair(
            marc_record=marc_pub,
            copyright_record=copyright_pub,
            match_type="registration",
            lccn="n78890351",
        )

        assert pair.marc_record == marc_pub
        assert pair.copyright_record == copyright_pub
        assert pair.match_type == "registration"
        assert pair.lccn == "n78890351"

    def test_pair_validation_no_marc_lccn(self):
        """Test validation fails when MARC record has no LCCN"""
        marc_pub = Publication("Test Title", source="MARC")  # No LCCN
        copyright_pub = Publication("Test Title", lccn="n78890351", source="Copyright")

        with pytest.raises(ValueError, match="MARC record must have normalized LCCN"):
            GroundTruthPair(
                marc_record=marc_pub,
                copyright_record=copyright_pub,
                match_type="registration",
                lccn="n78890351",
            )

    def test_pair_validation_no_copyright_lccn(self):
        """Test validation fails when copyright record has no LCCN"""
        marc_pub = Publication("Test Title", lccn="n78890351", source="MARC")
        copyright_pub = Publication("Test Title", source="Copyright")  # No LCCN

        with pytest.raises(ValueError, match="Copyright record must have normalized LCCN"):
            GroundTruthPair(
                marc_record=marc_pub,
                copyright_record=copyright_pub,
                match_type="registration",
                lccn="n78890351",
            )

    def test_pair_validation_mismatched_lccn(self):
        """Test validation fails when LCCNs don't match"""
        marc_pub = Publication("Test Title", lccn="n78890351", source="MARC")
        copyright_pub = Publication("Test Title", lccn="n79123456", source="Copyright")

        with pytest.raises(ValueError, match="LCCN values must match"):
            GroundTruthPair(
                marc_record=marc_pub,
                copyright_record=copyright_pub,
                match_type="registration",
                lccn="n78890351",
            )

    def test_pair_validation_invalid_match_type(self):
        """Test validation fails with invalid match type"""
        marc_pub = Publication("Test Title", lccn="n78890351", source="MARC")
        copyright_pub = Publication("Test Title", lccn="n78890351", source="Copyright")

        with pytest.raises(ValueError, match="Match type must be 'registration' or 'renewal'"):
            GroundTruthPair(
                marc_record=marc_pub,
                copyright_record=copyright_pub,
                match_type="invalid",
                lccn="n78890351",
            )


class TestGroundTruthStats:
    """Test the GroundTruthStats dataclass"""

    def test_stats_properties(self):
        """Test calculated properties of GroundTruthStats"""
        stats = GroundTruthStats(
            total_marc_records=1000,
            marc_with_lccn=100,
            total_copyright_records=500,
            copyright_with_lccn=50,
            total_renewal_records=200,
            registration_matches=25,
            renewal_matches=15,
            unique_lccns_matched=35,
        )

        assert stats.total_matches == 40
        assert stats.marc_lccn_coverage == 10.0
        assert stats.copyright_lccn_coverage == 10.0

    def test_stats_zero_division_handling(self):
        """Test that zero division is handled gracefully"""
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

        publications = [
            Publication("Title 1", lccn="n78890351", source="Test"),
            Publication("Title 2", lccn="n79123456", source="Test"),
            Publication("Title 3", source="Test"),  # No LCCN
            Publication("Title 4", lccn="n78890351", source="Test"),  # Duplicate LCCN
        ]

        index = extractor._build_lccn_index(publications)

        assert len(index) == 2
        assert "n78890351" in index
        assert "n79123456" in index
        assert len(index["n78890351"]) == 2  # Two publications with same LCCN
        assert len(index["n79123456"]) == 1

    def test_extract_ground_truth_pairs_basic(self):
        """Test basic ground truth pair extraction"""
        extractor = GroundTruthExtractor()

        # Create test data with matching LCCNs
        marc_records = [
            [Publication("MARC Title 1", lccn="n78890351", source="MARC")],
            [Publication("MARC Title 2", lccn="n79123456", source="MARC")],
            [Publication("MARC Title 3", source="MARC")],  # No LCCN
        ]

        copyright_records = [
            Publication(
                "Copyright Title 1", lccn="n78-890351", source="Copyright"
            ),  # Matches after normalization
            Publication("Copyright Title 4", lccn="n80999999", source="Copyright"),  # No match
        ]

        renewal_records = [
            Publication(
                "Renewal Title 2", lccn="n79-123456", source="Renewal"
            )  # Matches after normalization
        ]

        pairs, stats = extractor.extract_ground_truth_pairs(
            marc_records, copyright_records, renewal_records
        )

        # Should find 2 matches: 1 registration + 1 renewal
        assert len(pairs) == 2
        assert stats.total_matches == 2
        assert stats.registration_matches == 1
        assert stats.renewal_matches == 1
        assert stats.unique_lccns_matched == 2

        # Check the actual pairs
        registration_pair = next(p for p in pairs if p.match_type == "registration")
        renewal_pair = next(p for p in pairs if p.match_type == "renewal")

        assert registration_pair.lccn == "n78890351"
        assert renewal_pair.lccn == "n79123456"

    def test_extract_ground_truth_pairs_no_renewals(self):
        """Test extraction when no renewal data provided"""
        extractor = GroundTruthExtractor()

        marc_records = [[Publication("MARC Title", lccn="n78890351", source="MARC")]]

        copyright_records = [Publication("Copyright Title", lccn="n78890351", source="Copyright")]

        pairs, stats = extractor.extract_ground_truth_pairs(marc_records, copyright_records, None)

        assert len(pairs) == 1
        assert stats.registration_matches == 1
        assert stats.renewal_matches == 0
        assert stats.total_renewal_records == 0

    def test_filter_by_lccn_prefix(self):
        """Test filtering by LCCN prefix"""
        extractor = GroundTruthExtractor()

        # Create pairs with different prefixes
        pairs = [
            GroundTruthPair(
                marc_record=Publication("Title 1", lccn="n78890351", source="MARC"),
                copyright_record=Publication("Title 1", lccn="n78890351", source="Copyright"),
                match_type="registration",
                lccn="n78890351",
            ),
            GroundTruthPair(
                marc_record=Publication("Title 2", lccn="85000002", source="MARC"),
                copyright_record=Publication("Title 2", lccn="85000002", source="Copyright"),
                match_type="registration",
                lccn="85000002",
            ),
        ]

        # Filter for 'n' prefix
        n_pairs = extractor.filter_by_lccn_prefix(pairs, "n")
        assert len(n_pairs) == 1
        assert n_pairs[0].lccn == "n78890351"

        # Filter for empty prefix (numeric-only LCCNs)
        numeric_pairs = extractor.filter_by_lccn_prefix(pairs, "")
        assert len(numeric_pairs) == 1
        assert numeric_pairs[0].lccn == "85000002"

    def test_filter_by_year_range(self):
        """Test filtering by publication year range"""
        extractor = GroundTruthExtractor()

        pairs = [
            GroundTruthPair(
                marc_record=Publication(
                    "Title 1", lccn="n78890351", pub_date="1950", source="MARC"
                ),
                copyright_record=Publication("Title 1", lccn="n78890351", source="Copyright"),
                match_type="registration",
                lccn="n78890351",
            ),
            GroundTruthPair(
                marc_record=Publication(
                    "Title 2", lccn="n79123456", pub_date="1975", source="MARC"
                ),
                copyright_record=Publication("Title 2", lccn="n79123456", source="Copyright"),
                match_type="registration",
                lccn="n79123456",
            ),
        ]

        # Filter for 1960-1980
        filtered = extractor.filter_by_year_range(pairs, min_year=1960, max_year=1980)
        assert len(filtered) == 1
        assert filtered[0].marc_record.year == 1975

        # Filter for minimum year only
        filtered = extractor.filter_by_year_range(pairs, min_year=1960)
        assert len(filtered) == 1

        # Filter for maximum year only
        filtered = extractor.filter_by_year_range(pairs, max_year=1960)
        assert len(filtered) == 1
        assert filtered[0].marc_record.year == 1950

    def test_get_coverage_report(self):
        """Test coverage report generation"""
        extractor = GroundTruthExtractor()

        stats = GroundTruthStats(
            total_marc_records=1000,
            marc_with_lccn=100,
            total_copyright_records=500,
            copyright_with_lccn=50,
            total_renewal_records=200,
            registration_matches=25,
            renewal_matches=15,
            unique_lccns_matched=35,
        )

        report = extractor.get_coverage_report(stats)

        assert "LCCN Ground Truth Coverage Report" in report
        assert "Total: 1,000" in report
        assert "With LCCN: 100 (10.0%)" in report
        assert "Registration matches: 25" in report
        assert "Renewal matches: 15" in report
        assert "Total matches: 40" in report
        assert "Match rate: 40.0%" in report
