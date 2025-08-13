# tests/test_utils/test_lccn_utils.py

"""Test LCCN normalization utilities"""

# Third party imports

# Local imports
from marc_pd_tool.shared.utils.text_utils import extract_lccn_prefix
from marc_pd_tool.shared.utils.text_utils import extract_lccn_serial
from marc_pd_tool.shared.utils.text_utils import extract_lccn_year
from marc_pd_tool.shared.utils.text_utils import normalize_lccn


class TestNormalizeLccn:
    """Test LCCN normalization function with official examples"""

    def test_standard_examples(self):
        """Test all examples from Library of Congress specification"""
        # Official examples from the specification
        assert normalize_lccn("n78-890351") == "n78890351"
        assert normalize_lccn("n78-89035") == "n78089035"
        assert normalize_lccn("n 78890351 ") == "n78890351"
        assert normalize_lccn(" 85000002 ") == "85000002"
        assert normalize_lccn("85-2 ") == "85000002"
        assert normalize_lccn("2001-000002") == "2001000002"
        assert normalize_lccn("75-425165//r75") == "75425165"
        assert normalize_lccn(" 79139101 /AC/r932") == "79139101"

    def test_empty_and_none_inputs(self):
        """Test handling of empty and None inputs"""
        assert normalize_lccn("") == ""
        assert normalize_lccn(None) == ""

    def test_whitespace_removal(self):
        """Test removal of all blanks/spaces"""
        assert normalize_lccn("  n 78 890351  ") == "n78890351"
        assert normalize_lccn("85 000 002") == "85000002"
        assert normalize_lccn("   ") == ""

    def test_forward_slash_handling(self):
        """Test forward slash removal and everything after it"""
        assert normalize_lccn("75-425165//r75") == "75425165"
        assert normalize_lccn("79139101/AC/r932") == "79139101"
        assert normalize_lccn("n78-890351/test") == "n78890351"
        assert normalize_lccn("85000002/revision") == "85000002"

    def test_hyphen_handling_basic(self):
        """Test basic hyphen removal and zero-padding"""
        assert normalize_lccn("78-1") == "78000001"
        assert normalize_lccn("78-12") == "78000012"
        assert normalize_lccn("78-123") == "78000123"
        assert normalize_lccn("78-1234") == "78001234"
        assert normalize_lccn("78-12345") == "78012345"
        assert normalize_lccn("78-123456") == "78123456"

    def test_hyphen_handling_with_prefix(self):
        """Test hyphen handling with alphabetic prefixes"""
        assert normalize_lccn("n78-1") == "n78000001"
        assert normalize_lccn("abc78-123") == "abc78000123"
        assert normalize_lccn("x2001-45") == "x2001000045"

    def test_four_digit_years(self):
        """Test handling of four-digit years"""
        assert normalize_lccn("2001-000002") == "2001000002"
        assert normalize_lccn("1995-123") == "1995000123"
        assert normalize_lccn("2020-1") == "2020000001"

    def test_no_hyphen_cases(self):
        """Test cases without hyphens (no zero-padding needed)"""
        assert normalize_lccn("n78890351") == "n78890351"
        assert normalize_lccn("85000002") == "85000002"
        assert normalize_lccn("2001000002") == "2001000002"

    def test_complex_combinations(self):
        """Test complex cases with multiple operations"""
        assert normalize_lccn(" n78-89035 /test") == "n78089035"
        assert normalize_lccn("  85-2  //revision") == "85000002"
        assert normalize_lccn(" 2001-002 /AC/r932 ") == "2001000002"

    def test_edge_cases(self):
        """Test edge cases and malformed input"""
        # Multiple hyphens - all should be removed
        assert normalize_lccn("78-123-456") == "78123456"

        # Non-digit after hyphen (should not zero-pad)
        assert normalize_lccn("78-abc") == "78abc"

        # More than 6 digits after hyphen (should not zero-pad)
        assert normalize_lccn("78-1234567") == "781234567"

        # Only prefix
        assert normalize_lccn("n") == "n"
        assert normalize_lccn("abc") == "abc"


class TestExtractLccnPrefix:
    """Test LCCN prefix extraction"""

    def test_standard_prefixes(self):
        """Test extraction of alphabetic prefixes"""
        assert extract_lccn_prefix("n78890351") == "n"
        assert extract_lccn_prefix("abc78890351") == "abc"
        assert extract_lccn_prefix("x2001000002") == "x"

    def test_no_prefix(self):
        """Test cases with no alphabetic prefix"""
        assert extract_lccn_prefix("78890351") == ""
        assert extract_lccn_prefix("2001000002") == ""
        assert extract_lccn_prefix("85000002") == ""

    def test_empty_input(self):
        """Test empty input handling"""
        assert extract_lccn_prefix("") == ""

    def test_all_letters(self):
        """Test input with no digits"""
        assert extract_lccn_prefix("abc") == "abc"
        assert extract_lccn_prefix("n") == "n"


class TestExtractLccnYear:
    """Test LCCN year extraction"""

    def test_two_digit_years(self):
        """Test extraction of 2-digit years"""
        assert extract_lccn_year("n78890351") == "78"
        assert extract_lccn_year("85000002") == "85"
        assert extract_lccn_year("abc12345678") == "12"

    def test_four_digit_years(self):
        """Test extraction of 4-digit years"""
        assert extract_lccn_year("2001000002") == "2001"
        assert extract_lccn_year("1995123456") == "1995"
        assert extract_lccn_year("x2020000001") == "2020"

    def test_no_digits(self):
        """Test cases with no digits"""
        assert extract_lccn_year("abc") == ""
        assert extract_lccn_year("n") == ""
        assert extract_lccn_year("") == ""

    def test_short_numeric_parts(self):
        """Test cases with very short numeric parts"""
        assert extract_lccn_year("n1") == "1"
        assert extract_lccn_year("abc12") == "12"


class TestExtractLccnSerial:
    """Test LCCN serial number extraction"""

    def test_two_digit_year_serials(self):
        """Test serial extraction after 2-digit years"""
        assert extract_lccn_serial("n78890351") == "890351"
        assert extract_lccn_serial("85000002") == "000002"
        assert extract_lccn_serial("abc12345678") == "345678"

    def test_four_digit_year_serials(self):
        """Test serial extraction after 4-digit years"""
        assert extract_lccn_serial("2001000002") == "000002"
        assert extract_lccn_serial("1995123456") == "123456"
        assert extract_lccn_serial("x2020000001") == "000001"

    def test_no_serial(self):
        """Test cases with no serial number"""
        assert extract_lccn_serial("n78") == ""
        assert extract_lccn_serial("2001") == ""
        assert extract_lccn_serial("abc") == ""
        assert extract_lccn_serial("") == ""

    def test_short_serials(self):
        """Test cases with short or missing serials"""
        assert extract_lccn_serial("n1") == ""
        assert extract_lccn_serial("abc12") == ""
        assert extract_lccn_serial("781") == "1"


class TestLccnUtilsIntegration:
    """Integration tests for LCCN utilities working together"""

    def test_round_trip_parsing(self):
        """Test that parsing components gives consistent results"""
        test_cases = ["n78890351", "85000002", "2001000002", "abc12345678"]

        for lccn in test_cases:
            prefix = extract_lccn_prefix(lccn)
            year = extract_lccn_year(lccn)
            serial = extract_lccn_serial(lccn)

            # Verify we can reconstruct the essential parts
            if prefix and year and serial:
                reconstructed = prefix + year + serial
                assert reconstructed == lccn
            elif not prefix and year and serial:
                reconstructed = year + serial
                assert reconstructed == lccn

    def test_normalization_then_parsing(self):
        """Test parsing normalized LCCNs"""
        raw_lccn = "n78-89035"
        normalized = normalize_lccn(raw_lccn)

        assert normalized == "n78089035"
        assert extract_lccn_prefix(normalized) == "n"
        assert extract_lccn_year(normalized) == "78"
        assert extract_lccn_serial(normalized) == "089035"
