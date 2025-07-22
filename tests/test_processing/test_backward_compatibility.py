"""Test backward compatibility of the matching engine refactoring"""

# Third party imports
import pytest

# Local imports
from marc_pd_tool.data.publication import Publication
from marc_pd_tool.processing.generic_title_detector import GenericTitleDetector
from marc_pd_tool.processing.matching_engine import find_best_match


class TestBackwardCompatibility:
    """Test that the refactored matching engine produces identical results to the original"""

    def setup_method(self):
        """Set up test fixtures"""
        self.generic_detector = GenericTitleDetector()

    def test_find_best_match_signature_unchanged(self):
        """Test that the function signature remains unchanged for existing code"""
        marc_pub = Publication("Test Title", "Smith, John", pub_date="1950")
        copyright_pubs = [Publication("Test Title", "Smith, John", pub_date="1950")]

        # This should work exactly as before - no matching_engine parameter needed
        result = find_best_match(
            marc_pub, copyright_pubs, 80, 70, 2, 60, 95, 90, self.generic_detector
        )

        assert result is not None
        assert "similarity_scores" in result
        assert "marc_record" in result
        assert "copyright_record" in result

    def test_exact_match_behavior(self):
        """Test that exact matches behave identically to original implementation"""
        marc_pub = Publication("Test Title", "Smith, John", pub_date="1950")
        copyright_pub = Publication("Test Title", "Smith, John", pub_date="1950")

        result = find_best_match(
            marc_pub, [copyright_pub], 80, 70, 2, 60, 95, 90, self.generic_detector
        )

        assert result is not None
        assert result["similarity_scores"]["title"] == 100.0
        assert result["similarity_scores"]["author"] == 100.0
        assert result["similarity_scores"]["combined"] > 95.0

    def test_dual_author_scoring_compatibility(self):
        """Test that dual author scoring works as expected"""
        # Test case where 1xx author matches better than 245$c
        marc_pub = Publication(
            "Test Title",
            author="by Dr. John Smith Jr.",  # 245$c - less normalized
            main_author="Smith, John",  # 1xx - more normalized
            pub_date="1950",
        )
        copyright_pub = Publication("Test Title", "Smith, John", pub_date="1950")

        result = find_best_match(
            marc_pub, [copyright_pub], 80, 70, 2, 60, 95, 90, self.generic_detector
        )

        assert result is not None
        # Should use the better match (1xx field)
        assert result["similarity_scores"]["author"] > 90

    def test_year_filtering_compatibility(self):
        """Test that year filtering works as in original implementation"""
        marc_pub = Publication("Test Title", "Smith, John", pub_date="1950")

        # Within tolerance
        copyright_pub_close = Publication("Test Title", "Smith, John", pub_date="1951")
        result = find_best_match(
            marc_pub, [copyright_pub_close], 80, 70, 2, 60, 95, 90, self.generic_detector
        )
        assert result is not None

        # Outside tolerance
        copyright_pub_far = Publication("Test Title", "Smith, John", pub_date="1960")
        result = find_best_match(
            marc_pub, [copyright_pub_far], 80, 70, 2, 60, 95, 90, self.generic_detector
        )
        assert result is None

    def test_publisher_scoring_compatibility(self):
        """Test that publisher scoring works for both registrations and renewals"""
        marc_pub = Publication("Test Title", "Smith, John", publisher="Penguin", pub_date="1950")

        # Registration record (direct publisher comparison)
        reg_pub = Publication(
            "Test Title", "Smith, John", publisher="Penguin Books", pub_date="1950"
        )
        result = find_best_match(marc_pub, [reg_pub], 80, 70, 2, 60, 95, 90, self.generic_detector)
        assert result is not None
        assert result["similarity_scores"]["publisher"] >= 70

        # Renewal record (full_text comparison)
        ren_pub = Publication(
            "Test Title",
            "Smith, John",
            pub_date="1950",
            source="Renewal",
            full_text="Published by Penguin Books in New York",
        )
        result = find_best_match(marc_pub, [ren_pub], 80, 70, 2, 60, 95, 90, self.generic_detector)
        assert result is not None
        assert result["similarity_scores"]["publisher"] >= 70

    def test_generic_title_detection_compatibility(self):
        """Test that generic title detection affects scoring as expected"""
        # Generic title should use different weighting
        marc_pub = Publication(
            "Complete Works", "Smith, John", publisher="Penguin", pub_date="1950"
        )
        copyright_pub = Publication(
            "Complete Works", "Smith, John", publisher="Penguin", pub_date="1950"
        )

        result = find_best_match(
            marc_pub, [copyright_pub], 80, 70, 2, 60, 95, 90, self.generic_detector
        )

        assert result is not None
        assert result["generic_title_info"]["has_generic_title"] is True
        # Combined score should reflect generic title weighting (less emphasis on title)
        assert result["similarity_scores"]["combined"] > 85.0

    def test_thresholds_compatibility(self):
        """Test that all threshold parameters work as expected"""
        marc_pub = Publication("Test Title", "Smith, John", publisher="Penguin", pub_date="1950")
        copyright_pub = Publication(
            "Similar Title", "Jones, Bob", publisher="Random", pub_date="1950"
        )

        # Should fail title threshold
        result = find_best_match(
            marc_pub, [copyright_pub], 95, 70, 2, 60, 95, 90, self.generic_detector
        )
        assert result is None

        # Should fail author threshold
        result = find_best_match(
            marc_pub, [copyright_pub], 50, 95, 2, 60, 95, 90, self.generic_detector
        )
        assert result is None

        # Should fail publisher threshold
        result = find_best_match(
            marc_pub, [copyright_pub], 50, 50, 2, 95, 95, 90, self.generic_detector
        )
        assert result is None

        # Should pass with very low thresholds (using better similarity scores)
        marc_pub_better = Publication(
            "Test Title", "Smith, John", publisher="Penguin", pub_date="1950"
        )
        copyright_pub_better = Publication(
            "Test Title", "Smith, John", publisher="Penguin", pub_date="1950"
        )
        result = find_best_match(
            marc_pub_better, [copyright_pub_better], 80, 70, 2, 60, 95, 90, self.generic_detector
        )
        assert result is not None

    def test_early_exit_compatibility(self):
        """Test that early exit behavior works as expected"""
        marc_pub = Publication("Test Title", "Smith, John", pub_date="1950")

        # First match is perfect, second is also good
        perfect_match = Publication("Test Title", "Smith, John", pub_date="1950")
        good_match = Publication("Test Title", "Smith, John", pub_date="1951")

        result = find_best_match(
            marc_pub, [perfect_match, good_match], 80, 70, 2, 60, 95, 90, self.generic_detector
        )

        assert result is not None
        # Should have found the perfect match and exited early
        assert result["similarity_scores"]["title"] == 100.0
        assert result["similarity_scores"]["author"] == 100.0

    def test_full_title_usage_compatibility(self):
        """Test that full title construction (with parts) works correctly"""
        marc_pub = Publication(
            "Main Title", "Smith, John", pub_date="1950", part_number="1", part_name="Introduction"
        )
        copyright_pub = Publication(
            "Main Title. Part 1. Introduction", "Smith, John", pub_date="1950"
        )

        result = find_best_match(
            marc_pub, [copyright_pub], 80, 70, 2, 60, 95, 90, self.generic_detector
        )

        assert result is not None
        # Should get high title score due to full title matching
        assert result["similarity_scores"]["title"] > 90

    def test_result_structure_compatibility(self):
        """Test that the result structure is identical to the original"""
        marc_pub = Publication("Test Title", "Smith, John", pub_date="1950")
        copyright_pub = Publication("Test Title", "Smith, John", pub_date="1950")

        result = find_best_match(
            marc_pub, [copyright_pub], 80, 70, 2, 60, 95, 90, self.generic_detector
        )

        assert result is not None

        # Check all expected keys exist
        expected_keys = [
            "marc_record",
            "copyright_record",
            "similarity_scores",
            "generic_title_info",
        ]
        for key in expected_keys:
            assert key in result

        # Check similarity_scores structure
        similarity_keys = ["title", "author", "publisher", "combined"]
        for key in similarity_keys:
            assert key in result["similarity_scores"]
            assert isinstance(result["similarity_scores"][key], (int, float))

        # Check generic_title_info structure
        generic_keys = [
            "marc_title_is_generic",
            "copyright_title_is_generic",
            "has_generic_title",
            "marc_detection_reason",
            "copyright_detection_reason",
        ]
        for key in generic_keys:
            assert key in result["generic_title_info"]

    def test_none_result_compatibility(self):
        """Test that None is returned when no match is found, just like original"""
        marc_pub = Publication("Test Title", "Smith, John", pub_date="1950")
        copyright_pub = Publication("Completely Different", "Doe, Jane", pub_date="1960")

        result = find_best_match(
            marc_pub, [copyright_pub], 80, 70, 2, 60, 95, 90, self.generic_detector
        )

        assert result is None

    def test_empty_list_compatibility(self):
        """Test behavior with empty copyright publications list"""
        marc_pub = Publication("Test Title", "Smith, John", pub_date="1950")

        result = find_best_match(marc_pub, [], 80, 70, 2, 60, 95, 90, self.generic_detector)

        assert result is None

    def test_missing_data_compatibility(self):
        """Test handling of missing data fields"""
        # Publication with minimal data
        marc_pub = Publication("Test Title")  # No author, year, publisher
        copyright_pub = Publication("Test Title")

        result = find_best_match(
            marc_pub, [copyright_pub], 80, 70, 2, 60, 95, 90, self.generic_detector
        )

        assert result is not None
        assert result["similarity_scores"]["title"] == 100.0
        assert result["similarity_scores"]["author"] == 0.0  # No author data
        assert result["similarity_scores"]["publisher"] == 0.0  # No publisher data
