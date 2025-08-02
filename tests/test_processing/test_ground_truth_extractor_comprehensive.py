# tests/test_processing/test_ground_truth_extractor_comprehensive.py

"""Comprehensive tests for ground_truth_extractor.py to achieve 100% coverage"""

# Standard library imports
from unittest.mock import Mock
from unittest.mock import patch
from unittest.mock import MagicMock

# Third party imports
import pytest

# Local imports
from marc_pd_tool.processing.ground_truth_extractor import GroundTruthExtractor
from marc_pd_tool.data.ground_truth import GroundTruthPair
from marc_pd_tool.data.ground_truth import GroundTruthStats
from marc_pd_tool.data.publication import Publication


class TestGroundTruthExtractorComprehensive:
    """Comprehensive tests for GroundTruthExtractor"""
    
    def test_init(self):
        """Test initialization"""
        extractor = GroundTruthExtractor()
        assert extractor.logger is not None
        assert extractor.logger.name == "GroundTruthExtractor"
    
    def test_extract_with_none_renewal_publications(self):
        """Test extraction when renewal_publications is None"""
        marc_pub = Publication(
            title="Test Book",
            author="Test Author",
            pub_date="1975",
            source_id="m001",
            lccn="75012345"
        )
        marc_pub.normalized_lccn = "75012345"
        marc_pub.year = 1975
        
        copyright_pub = Publication(
            title="Test Book",
            author="Test Author",
            pub_date="1975",
            source_id="c001",
            lccn="75012345"
        )
        copyright_pub.normalized_lccn = "75012345"
        copyright_pub.year = 1975
        
        extractor = GroundTruthExtractor()
        # Pass None for renewal_publications
        pairs, stats = extractor.extract_ground_truth_pairs(
            [[marc_pub]],
            [copyright_pub],
            None  # This should trigger line 40
        )
        
        assert len(pairs) == 1
        assert pairs[0].match_type == "registration"
        assert stats.total_renewal_records == 0
    
    def test_extract_ground_truth_pairs_basic(self):
        """Test basic ground truth extraction"""
        # Create test MARC publications
        marc_pub = Publication(
            title="Test Book",
            author="Test Author",
            pub_date="1975",
            source_id="m001",
            lccn="   75012345 "
        )
        marc_pub.normalized_lccn = "75012345"
        marc_pub.year = 1975
        
        # Create test copyright publication with matching LCCN
        copyright_pub = Publication(
            title="Test Book",
            author="Test Author",
            pub_date="1975",
            source_id="c001",
            lccn="75012345"
        )
        copyright_pub.normalized_lccn = "75012345"
        copyright_pub.year = 1975
        
        extractor = GroundTruthExtractor()
        pairs, stats = extractor.extract_ground_truth_pairs(
            [[marc_pub]],  # marc_batches is a list of lists
            [copyright_pub],  # copyright_publications
            []  # renewal_publications
        )
        
        assert len(pairs) == 1
        assert pairs[0].marc_record.normalized_lccn == "75012345"
        assert pairs[0].copyright_record.normalized_lccn == "75012345"
        assert pairs[0].match_type == "registration"
        assert stats.marc_with_lccn == 1
        assert stats.registration_matches == 1
    
    def test_extract_with_no_matches(self):
        """Test extraction when there are no LCCN matches"""
        # Create test MARC publications
        marc_pub1 = Publication(
            title="Book 1",
            author="Author 1",
            pub_date="1950",
            source_id="m001",
            lccn="50012345"
        )
        marc_pub1.normalized_lccn = "50012345"
        marc_pub1.year = 1950
        
        marc_pub2 = Publication(
            title="Book 2",
            author="Author 2",
            pub_date="1975",
            source_id="m002",
            lccn="75012345"
        )
        marc_pub2.normalized_lccn = "75012345"
        marc_pub2.year = 1975
        
        # Create copyright publications with different LCCNs
        copyright_pub = Publication(
            title="Different Book",
            author="Different Author",
            pub_date="1960",
            source_id="c001",
            lccn="60054321"
        )
        copyright_pub.normalized_lccn = "60054321"
        copyright_pub.year = 1960
        
        extractor = GroundTruthExtractor()
        
        # Extract - should find no matches
        pairs, stats = extractor.extract_ground_truth_pairs(
            [[marc_pub1, marc_pub2]],
            [copyright_pub],
            []
        )
        
        assert len(pairs) == 0
        assert stats.marc_with_lccn == 2  # Both MARC records have LCCN
        assert stats.registration_matches == 0  # No matches found
    
    def test_extract_with_renewal_matches(self):
        """Test extraction with renewal matches"""
        # Create test MARC publication
        marc_pub = Publication(
            title="Renewed Book",
            author="Author",
            pub_date="1955",
            source_id="m001",
            lccn="55012345"
        )
        marc_pub.normalized_lccn = "55012345"
        marc_pub.year = 1955
        
        # Create renewal publication with matching LCCN in oreg field
        renewal_pub = Publication(
            title="Renewed Book",
            author="Author",
            pub_date="1955",  # Original date
            source_id="R123456"
        )
        # For renewal records to match via LCCN, they need the LCCN field
        renewal_pub.lccn = "55012345"
        renewal_pub.normalized_lccn = "55012345"
        renewal_pub.year = 1955
        
        extractor = GroundTruthExtractor()
        pairs, stats = extractor.extract_ground_truth_pairs(
            [[marc_pub]],
            [],  # No copyright records
            [renewal_pub]
        )
        
        assert len(pairs) == 1
        assert pairs[0].match_type == "renewal"
        # GroundTruthPair uses copyright_record for both registration and renewal
        assert pairs[0].copyright_record is not None
        assert stats.renewal_matches == 1
    
    def test_build_lccn_index(self):
        """Test LCCN index building"""
        extractor = GroundTruthExtractor()
        
        # Create test publications
        pubs = [
            Publication(
                title="Book 1",
                author="Author 1",
                pub_date="1950",
                source_id="001",
                lccn="  50012345  "
            ),
            Publication(
                title="Book 2",
                author="Author 2",
                pub_date="1960",
                source_id="002",
                lccn="60054321"
            ),
            Publication(
                title="Book 3",
                author="Author 3",
                pub_date="1970",
                source_id="003"
                # No LCCN
            )
        ]
        
        # Normalize LCCNs
        for pub in pubs:
            if pub.lccn:
                pub.normalized_lccn = pub.lccn.strip()
        
        index = extractor._build_lccn_index(pubs)
        
        assert len(index) == 2
        assert "50012345" in index
        assert "60054321" in index
        # Index maps to list of publications
        assert len(index["50012345"]) == 1
        # Title is normalized to lowercase
        assert index["50012345"][0].title == "book 1"
    
    def test_extract_with_both_copyright_and_renewal_matches(self):
        """Test extraction when a record matches both copyright and renewal"""
        # Create test MARC publication
        marc_pub = Publication(
            title="Double Match Book",
            author="Author",
            pub_date="1955",
            source_id="m001",
            lccn="55012345"
        )
        marc_pub.normalized_lccn = "55012345"
        marc_pub.year = 1955
        
        # Create matching copyright publication
        copyright_pub = Publication(
            title="Double Match Book",
            author="Author",
            pub_date="1955",
            source_id="A55012345",
            lccn="55012345"
        )
        copyright_pub.normalized_lccn = "55012345"
        copyright_pub.year = 1955
        
        # Create matching renewal publication
        renewal_pub = Publication(
            title="Double Match Book",
            author="Author",
            pub_date="1955",
            source_id="R123456"
        )
        renewal_pub.lccn = "55012345" 
        renewal_pub.normalized_lccn = "55012345"
        renewal_pub.year = 1955
        
        extractor = GroundTruthExtractor()
        pairs, stats = extractor.extract_ground_truth_pairs(
            [[marc_pub]],
            [copyright_pub],
            [renewal_pub]
        )
        
        # With current implementation, this creates two separate pairs
        assert len(pairs) == 2  # One for registration, one for renewal
        assert pairs[0].match_type == "registration"
        assert pairs[1].match_type == "renewal"
        assert stats.registration_matches == 1
        assert stats.renewal_matches == 1
    
    def test_empty_inputs(self):
        """Test extraction with empty inputs"""
        extractor = GroundTruthExtractor()
        
        # Test with empty lists
        pairs, stats = extractor.extract_ground_truth_pairs(
            [],  # No MARC batches
            [],  # No copyright records
            []   # No renewal records
        )
        
        assert len(pairs) == 0
        assert stats.total_marc_records == 0
        assert stats.marc_with_lccn == 0
        assert stats.registration_matches == 0
        assert stats.renewal_matches == 0
        # both_matches is not a property of GroundTruthStats
        assert stats.registration_matches == 0
        assert stats.renewal_matches == 0
    
    def test_invalid_ground_truth_pair(self):
        """Test handling of invalid ground truth pairs"""
        # Create MARC publication with LCCN
        marc_pub = Publication(
            title="Test Book",
            author="Author",
            pub_date="1975",
            source_id="m001",
            lccn="75012345"
        )
        marc_pub.normalized_lccn = "75012345"
        marc_pub.year = 1975
        
        # Create copyright publication with mismatched LCCN
        copyright_pub = Publication(
            title="Different Book",
            author="Author",
            pub_date="1975",
            source_id="c001",
            lccn="75054321"  # Different LCCN
        )
        copyright_pub.normalized_lccn = "75054321"
        copyright_pub.year = 1975
        
        # Create renewal with no normalized LCCN
        renewal_pub = Publication(
            title="Renewal Book",
            author="Author",
            pub_date="1975",
            source_id="r001"
        )
        # No normalized_lccn set
        
        extractor = GroundTruthExtractor()
        
        # Manually build indexes with mismatched data
        copyright_index = {"75012345": [copyright_pub]}  # Wrong LCCN in index
        renewal_index = {"75012345": [renewal_pub]}  # No normalized LCCN
        
        # Mock the index building to return our bad data
        with patch.object(extractor, '_build_lccn_index') as mock_build:
            mock_build.side_effect = [copyright_index, renewal_index]
            
            pairs, stats = extractor.extract_ground_truth_pairs(
                [[marc_pub]],
                [copyright_pub],
                [renewal_pub]
            )
            
            # Should have no pairs due to validation errors
            assert len(pairs) == 0
            assert stats.registration_matches == 0
            assert stats.renewal_matches == 0
    
    def test_filter_by_year_range(self):
        """Test year range filtering of ground truth pairs"""
        extractor = GroundTruthExtractor()
        
        # Create pairs with different years
        pairs = []
        for year in [1950, 1960, 1970, 1980, None]:
            marc = Publication(
                title=f"Book {year}",
                pub_date=str(year) if year else None,
                source_id=f"m{year}",
                lccn=f"{year}001" if year else "none001"
            )
            marc.normalized_lccn = marc.lccn
            marc.year = year
            
            copyright = Publication(
                title=f"Book {year}",
                pub_date=str(year) if year else None,
                source_id=f"c{year}",
                lccn=f"{year}001" if year else "none001"
            )
            copyright.normalized_lccn = copyright.lccn
            copyright.year = year
            
            pair = GroundTruthPair(
                marc_record=marc,
                copyright_record=copyright,
                match_type="registration",
                lccn=marc.lccn
            )
            pairs.append(pair)
        
        # Test different filters
        filtered = extractor.filter_by_year_range(pairs, 1960, 1970)
        assert len(filtered) == 2  # 1960 and 1970
        
        filtered = extractor.filter_by_year_range(pairs, 1965, None)
        assert len(filtered) == 2  # 1970 and 1980
        
        filtered = extractor.filter_by_year_range(pairs, None, 1955)
        assert len(filtered) == 1  # 1950
        
        filtered = extractor.filter_by_year_range(pairs, None, None)
        assert len(filtered) == 4  # All except None
    
    def test_get_coverage_report(self):
        """Test coverage report generation"""
        extractor = GroundTruthExtractor()
        
        # Create stats
        stats = GroundTruthStats(
            total_marc_records=1000,
            marc_with_lccn=800,
            total_copyright_records=5000,
            copyright_with_lccn=4000,
            total_renewal_records=2000,
            registration_matches=600,
            renewal_matches=100,
            unique_lccns_matched=650
        )
        
        report = extractor.get_coverage_report(stats)
        
        # Check report contains expected information
        assert "LCCN Ground Truth Coverage Report" in report
        assert "MARC Records:" in report
        assert "Total: 1,000" in report
        assert "With LCCN: 800 (80.0%)" in report
        assert "Copyright Registration Records:" in report
        assert "Total: 5,000" in report
        assert "With LCCN: 4,000 (80.0%)" in report
        assert "Registration matches: 600" in report
        assert "Renewal matches: 100" in report
        assert "Total matches: 700" in report
        assert "Match rate: 87.5% of MARC records with LCCN" in report
    
    def test_get_coverage_report_no_marc_with_lccn(self):
        """Test coverage report when no MARC records have LCCN"""
        extractor = GroundTruthExtractor()
        
        stats = GroundTruthStats(
            total_marc_records=100,
            marc_with_lccn=0,
            total_copyright_records=500,
            copyright_with_lccn=400,
            total_renewal_records=200,
            registration_matches=0,
            renewal_matches=0,
            unique_lccns_matched=0
        )
        
        report = extractor.get_coverage_report(stats)
        
        # Should handle division by zero gracefully
        assert "With LCCN: 0 (0.0%)" in report
        # Match rate line should be omitted when marc_with_lccn is 0
        assert "Match rate:" not in report

    def test_marc_without_lccn(self):
        """Test extraction with MARC records that lack LCCN"""
        # Create MARC publications, some without LCCN
        marc_with_lccn = Publication(
            title="Book with LCCN",
            author="Author",
            pub_date="1975",
            source_id="m001",
            lccn="75012345"
        )
        marc_with_lccn.normalized_lccn = "75012345"
        marc_with_lccn.year = 1975
        
        marc_without_lccn = Publication(
            title="Book without LCCN",
            author="Author",
            pub_date="1975",
            source_id="m002"
            # No LCCN
        )
        marc_without_lccn.year = 1975
        
        # Create matching copyright
        copyright_pub = Publication(
            title="Book with LCCN",
            author="Author",
            pub_date="1975",
            source_id="c001",
            lccn="75012345"
        )
        copyright_pub.normalized_lccn = "75012345"
        copyright_pub.year = 1975
        
        extractor = GroundTruthExtractor()
        pairs, stats = extractor.extract_ground_truth_pairs(
            [[marc_with_lccn, marc_without_lccn]],
            [copyright_pub],
            []
        )
        
        assert len(pairs) == 1  # Only one match
        assert pairs[0].marc_record.source_id == "m001"
        assert stats.total_marc_records == 2
        assert stats.marc_with_lccn == 1  # Only one has LCCN
        # marc_without_lccn is not tracked in GroundTruthStats