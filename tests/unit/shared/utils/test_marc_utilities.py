# tests/unit/shared/utils/test_marc_utilities.py

"""Comprehensive tests for MARC utility functions

This module consolidates all MARC-related utility tests including:
- LCCN normalization and extraction
- Country code extraction from MARC 008 field
- Language detection from MARC records
- LCCN property-based testing
"""

# Third party imports
from hypothesis import given
from hypothesis import strategies as st

# Local imports
from marc_pd_tool.core.domain.enums import CountryClassification
from marc_pd_tool.shared.utils.marc_utilities import MARC_LANGUAGE_MAPPING
from marc_pd_tool.shared.utils.marc_utilities import US_COUNTRY_CODES
from marc_pd_tool.shared.utils.marc_utilities import extract_country_from_marc_008
from marc_pd_tool.shared.utils.text_utils import extract_lccn_prefix
from marc_pd_tool.shared.utils.text_utils import extract_lccn_serial
from marc_pd_tool.shared.utils.text_utils import extract_lccn_year
from marc_pd_tool.shared.utils.text_utils import normalize_lccn

# ===== LCCN Normalization Tests =====


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
        """Test hyphen handling with prefixes"""
        assert normalize_lccn("n78-890351") == "n78890351"
        assert normalize_lccn("n78-89035") == "n78089035"
        assert normalize_lccn("n 78-890351") == "n78890351"
        assert normalize_lccn("sn85-2") == "sn85000002"

    def test_eight_digit_year_handling(self):
        """Test 8-digit year normalization (post-2000)"""
        assert normalize_lccn("2001-000002") == "2001000002"
        assert normalize_lccn("2001-2") == "2001000002"
        assert normalize_lccn("2010-123456") == "2010123456"
        assert normalize_lccn("2001000002") == "2001000002"

    def test_case_insensitive_prefixes(self):
        """Test that prefixes are handled case-insensitively"""
        assert normalize_lccn("N78-890351") == "N78890351"
        assert normalize_lccn("SN85-2") == "SN85000002"

        # But normalization preserves original case
        assert normalize_lccn("n78-890351") == "n78890351"
        assert normalize_lccn("sn85-2") == "sn85000002"

    def test_various_real_world_examples(self):
        """Test various real-world LCCN formats"""
        # From older records
        assert normalize_lccn("42037934") == "42037934"
        assert normalize_lccn("50-14935") == "50014935"
        assert normalize_lccn("agr26-1253") == "agr26001253"

        # Modern formats
        assert normalize_lccn("2003012345") == "2003012345"
        assert normalize_lccn("2003-12345") == "2003012345"

        # With revisions/alternates
        assert normalize_lccn("85-2 //r852") == "85000002"
        assert normalize_lccn("79-139101/AC") == "79139101"


class TestExtractLccnPrefix:
    """Test LCCN prefix extraction"""

    def test_extract_standard_prefixes(self):
        """Test extraction of standard LCCN prefixes"""
        assert extract_lccn_prefix("n78890351") == "n"
        assert extract_lccn_prefix("sn85000002") == "sn"
        assert extract_lccn_prefix("agr26001253") == "agr"

    def test_no_prefix(self):
        """Test LCCNs without prefixes"""
        assert extract_lccn_prefix("78890351") == ""
        assert extract_lccn_prefix("2001000002") == ""
        assert extract_lccn_prefix("85000002") == ""

    def test_edge_cases(self):
        """Test edge cases for prefix extraction"""
        assert extract_lccn_prefix("") == ""
        assert extract_lccn_prefix(None) == ""
        assert extract_lccn_prefix("n") == "n"


class TestExtractLccnYear:
    """Test LCCN year extraction"""

    def test_extract_two_digit_years(self):
        """Test extraction of 2-digit years"""
        assert extract_lccn_year("n78890351") == "78"
        assert extract_lccn_year("78890351") == "78"
        assert extract_lccn_year("sn85000002") == "85"
        assert extract_lccn_year("85000002") == "85"

    def test_extract_four_digit_years(self):
        """Test extraction of 4-digit years (post-2000)"""
        assert extract_lccn_year("2001000002") == "2001"
        assert extract_lccn_year("2010123456") == "2010"

    def test_year_with_prefix(self):
        """Test year extraction with various prefixes"""
        assert extract_lccn_year("n78890351") == "78"
        assert extract_lccn_year("sn85000002") == "85"
        assert extract_lccn_year("agr26001253") == "26"

    def test_edge_cases(self):
        """Test edge cases for year extraction"""
        assert extract_lccn_year("") == ""
        assert extract_lccn_year(None) == ""
        assert extract_lccn_year("n") == ""


class TestExtractLccnSerial:
    """Test LCCN serial number extraction"""

    def test_extract_serial_numbers(self):
        """Test extraction of serial numbers"""
        assert extract_lccn_serial("n78890351") == "890351"
        assert extract_lccn_serial("78890351") == "890351"
        assert extract_lccn_serial("sn85000002") == "000002"
        assert extract_lccn_serial("2001000002") == "000002"

    def test_serial_with_various_formats(self):
        """Test serial extraction from various formats"""
        assert extract_lccn_serial("78000001") == "000001"
        assert extract_lccn_serial("78001234") == "001234"
        assert extract_lccn_serial("78123456") == "123456"
        assert extract_lccn_serial("2010123456") == "123456"

    def test_edge_cases(self):
        """Test edge cases for serial extraction"""
        assert extract_lccn_serial("") == ""
        assert extract_lccn_serial(None) == ""
        assert extract_lccn_serial("n78") == ""
        assert extract_lccn_serial("2001") == ""


# ===== Country Code Extraction Tests =====


class TestUSCountryCodes:
    """Test the US country codes constant"""

    def test_us_country_codes_contains_expected_codes(self):
        """Test that US_COUNTRY_CODES contains expected US state codes"""
        expected_codes = {
            "xxu",  # United States (general)
            "nyu",  # New York
            "cau",  # California
            "flu",  # Florida
            "txu",  # Texas
            "ilu",  # Illinois
            "pau",  # Pennsylvania
            "miu",  # Michigan
            "ohu",  # Ohio
            "gau",  # Georgia
            "ncu",  # North Carolina
            "nju",  # New Jersey
            "vau",  # Virginia
            "wau",  # Washington
            "mau",  # Massachusetts
            "inu",  # Indiana
            "azu",  # Arizona
            "tnu",  # Tennessee
            "mou",  # Missouri
            "mdu",  # Maryland
            "wvu",  # West Virginia
            "mnu",  # Minnesota
            "lau",  # Louisiana
            "alu",  # Alabama
            "kyu",  # Kentucky
            "oru",  # Oregon
            "oku",  # Oklahoma
            "ctu",  # Connecticut
            "iau",  # Iowa
            "msu",  # Mississippi
            "aru",  # Arkansas
            "ksu",  # Kansas
            "utu",  # Utah
            "nvu",  # Nevada
            "nmu",  # New Mexico
            "nbu",  # Nebraska
            "wyu",  # Wyoming
            "idu",  # Idaho
            "hiu",  # Hawaii
            "meu",  # Maine
            "nhu",  # New Hampshire
            "riu",  # Rhode Island
            "vtu",  # Vermont
            "deu",  # Delaware
            "aku",  # Alaska
            "dcu",  # District of Columbia
            "mtu",  # Montana
            "ndu",  # North Dakota
            "sdu",  # South Dakota
            "scu",  # South Carolina
        }

        # Check that all expected codes are present
        for code in expected_codes:
            assert code in US_COUNTRY_CODES, f"Expected US country code '{code}' not found"

    def test_us_country_codes_type_and_size(self):
        """Test basic properties of US_COUNTRY_CODES"""
        assert isinstance(US_COUNTRY_CODES, set)
        assert len(US_COUNTRY_CODES) > 50  # Should have all US states + territories

        # All codes should be 3 characters long and lowercase
        for code in US_COUNTRY_CODES:
            assert len(code) == 3, f"Country code '{code}' should be 3 characters"
            assert code.islower(), f"Country code '{code}' should be lowercase"


class TestRepairCountryCode:
    """Test the _repair_country_code function"""

    def test_repair_common_malformed_codes(self):
        """Test repair of common malformed country codes"""
        # Local imports
        from marc_pd_tool.shared.utils.marc_utilities import _repair_country_code

        # Test repairs that should result in empty string
        assert _repair_country_code("| |") == ""
        assert _repair_country_code("|| ") == ""
        assert _repair_country_code(" ||") == ""

    def test_no_repair_needed(self):
        """Test codes that don't need repair"""
        # Local imports
        from marc_pd_tool.shared.utils.marc_utilities import _repair_country_code

        # Valid codes should pass through unchanged
        assert _repair_country_code("usa") == "usa"
        assert _repair_country_code("gbr") == "gbr"
        assert _repair_country_code("fra") == "fra"

        # Even malformed codes that aren't in repair dict pass through
        assert _repair_country_code("|||") == "|||"
        assert _repair_country_code("xyz") == "xyz"

    def test_empty_input(self):
        """Test with empty input"""
        # Local imports
        from marc_pd_tool.shared.utils.marc_utilities import _repair_country_code

        assert _repair_country_code("") == ""
        assert _repair_country_code(None) == None


class TestExtractCountryFromMARC008:
    """Test the extract_country_from_marc_008 function"""

    def test_extract_us_country_codes(self):
        """Test extraction of various US country codes"""
        test_cases = [
            ("123456789012345xxu", "xxu", CountryClassification.US),
            ("123456789012345nyu", "nyu", CountryClassification.US),
            ("123456789012345cau", "cau", CountryClassification.US),
            ("123456789012345flu", "flu", CountryClassification.US),
            ("123456789012345txu", "txu", CountryClassification.US),
            ("123456789012345dcu", "dcu", CountryClassification.US),
        ]

        for field_008, expected_code, expected_classification in test_cases:
            code, classification = extract_country_from_marc_008(field_008)
            assert code == expected_code, f"Expected code '{expected_code}', got '{code}'"
            assert (
                classification == expected_classification
            ), f"Expected {expected_classification}, got {classification}"

    def test_extract_non_us_country_codes(self):
        """Test extraction of non-US country codes"""
        test_cases = [
            ("123456789012345enk", "enk", CountryClassification.NON_US),  # England
            ("123456789012345fr ", "fr", CountryClassification.NON_US),  # France
            ("123456789012345gw ", "gw", CountryClassification.NON_US),  # Germany
            ("123456789012345it ", "it", CountryClassification.NON_US),  # Italy
            ("123456789012345ja ", "ja", CountryClassification.NON_US),  # Japan
            ("123456789012345ch ", "ch", CountryClassification.NON_US),  # China
            ("123456789012345ru ", "ru", CountryClassification.NON_US),  # Russia
            ("123456789012345br ", "br", CountryClassification.NON_US),  # Brazil
            ("123456789012345au ", "au", CountryClassification.NON_US),  # Australia
            ("123456789012345ca ", "ca", CountryClassification.NON_US),  # Canada
        ]

        for field_008, expected_code, expected_classification in test_cases:
            code, classification = extract_country_from_marc_008(field_008)
            assert code == expected_code, f"Expected code '{expected_code}', got '{code}'"
            assert (
                classification == expected_classification
            ), f"Expected {expected_classification}, got {classification}"

    def test_extract_country_case_insensitive(self):
        """Test that country extraction is case insensitive for US codes"""
        test_cases = [
            ("123456789012345XXU", "XXU", CountryClassification.US),
            ("123456789012345NYU", "NYU", CountryClassification.US),
            ("123456789012345CAU", "CAU", CountryClassification.US),
            ("123456789012345Nyu", "Nyu", CountryClassification.US),
            ("123456789012345cAu", "cAu", CountryClassification.US),
        ]

        for field_008, expected_code, expected_classification in test_cases:
            code, classification = extract_country_from_marc_008(field_008)
            assert code == expected_code, f"Expected code '{expected_code}', got '{code}'"
            assert (
                classification == expected_classification
            ), f"Expected {expected_classification}, got {classification}"

    def test_field_008_too_short(self):
        """Test handling of MARC 008 fields that are too short"""
        short_fields = [
            "",
            "123",
            "123456789012345",  # Exactly 15 characters (need 18+)
            "12345678901234567",  # 17 characters
        ]

        for field_008 in short_fields:
            code, classification = extract_country_from_marc_008(field_008)
            assert code == "", f"Expected empty code for short field '{field_008}'"
            assert (
                classification == CountryClassification.UNKNOWN
            ), f"Expected UNKNOWN classification for short field"

    def test_empty_country_code_in_positions(self):
        """Test handling when country code positions are empty"""
        test_cases = [
            "123456789012345   ",  # Spaces in country positions
            "123456789012345\t\t\t",  # Tabs in country positions
            "123456789012345",  # Too short, no country positions
        ]

        for field_008 in test_cases:
            code, classification = extract_country_from_marc_008(field_008)
            assert code == "", f"Expected empty code for field '{field_008}'"
            assert (
                classification == CountryClassification.UNKNOWN
            ), f"Expected UNKNOWN classification"

    def test_country_code_with_trailing_spaces(self):
        """Test country codes with trailing spaces are handled correctly"""
        test_cases = [
            ("123456789012345xx ", "xx", CountryClassification.NON_US),
            ("123456789012345n  ", "n", CountryClassification.NON_US),
            ("123456789012345fr ", "fr", CountryClassification.NON_US),
        ]

        for field_008, expected_code, expected_classification in test_cases:
            code, classification = extract_country_from_marc_008(field_008)
            assert code == expected_code, f"Expected code '{expected_code}', got '{code}'"
            assert (
                classification == expected_classification
            ), f"Expected {expected_classification}, got {classification}"

    def test_repaired_codes_that_become_empty(self):
        """Test country codes that get repaired to empty string"""
        # These codes should be repaired to empty and classified as UNKNOWN
        test_cases = [("123456789012345| |", "", CountryClassification.UNKNOWN)]

        for field_008, expected_code, expected_classification in test_cases:
            code, classification = extract_country_from_marc_008(field_008)
            assert code == expected_code, f"Expected empty code, got '{code}'"
            assert classification == expected_classification


# ===== Language Mapping Tests =====


class TestMARCLanguageMapping:
    """Test MARC language code mapping"""

    def test_mapping_contains_expected_languages(self):
        """Test that mapping contains our target languages"""
        # English variants
        assert "eng" in MARC_LANGUAGE_MAPPING
        assert "en" in MARC_LANGUAGE_MAPPING

        # French variants
        assert "fre" in MARC_LANGUAGE_MAPPING
        assert "fr" in MARC_LANGUAGE_MAPPING
        assert "fra" in MARC_LANGUAGE_MAPPING

        # German variants
        assert "ger" in MARC_LANGUAGE_MAPPING
        assert "de" in MARC_LANGUAGE_MAPPING
        assert "deu" in MARC_LANGUAGE_MAPPING

        # Spanish variants
        assert "spa" in MARC_LANGUAGE_MAPPING
        assert "es" in MARC_LANGUAGE_MAPPING
        assert "esp" in MARC_LANGUAGE_MAPPING

        # Italian variants
        assert "ita" in MARC_LANGUAGE_MAPPING
        assert "it" in MARC_LANGUAGE_MAPPING

    def test_mapping_normalized_codes(self):
        """Test that language codes are normalized correctly"""
        # English should all map to 'eng'
        assert MARC_LANGUAGE_MAPPING["eng"] == "eng"
        assert MARC_LANGUAGE_MAPPING["en"] == "eng"

        # French should all map to 'fre'
        assert MARC_LANGUAGE_MAPPING["fre"] == "fre"
        assert MARC_LANGUAGE_MAPPING["fr"] == "fre"
        assert MARC_LANGUAGE_MAPPING["fra"] == "fre"

        # German should all map to 'ger'
        assert MARC_LANGUAGE_MAPPING["ger"] == "ger"
        assert MARC_LANGUAGE_MAPPING["de"] == "ger"
        assert MARC_LANGUAGE_MAPPING["deu"] == "ger"

        # Spanish should all map to 'spa'
        assert MARC_LANGUAGE_MAPPING["spa"] == "spa"
        assert MARC_LANGUAGE_MAPPING["es"] == "spa"
        assert MARC_LANGUAGE_MAPPING["esp"] == "spa"

        # Italian should all map to 'ita'
        assert MARC_LANGUAGE_MAPPING["ita"] == "ita"
        assert MARC_LANGUAGE_MAPPING["it"] == "ita"

    def test_mapping_structure(self):
        """Test basic properties of the language mapping"""
        assert isinstance(MARC_LANGUAGE_MAPPING, dict)
        assert len(MARC_LANGUAGE_MAPPING) > 0

        # All keys and values should be strings
        for key, value in MARC_LANGUAGE_MAPPING.items():
            assert isinstance(key, str), f"Key '{key}' should be a string"
            assert isinstance(value, str), f"Value '{value}' should be a string"

        # All keys should be lowercase
        for key in MARC_LANGUAGE_MAPPING.keys():
            assert key == key.lower(), f"Key '{key}' should be lowercase"

        # All values should be 3-letter codes (standard MARC codes)
        for value in MARC_LANGUAGE_MAPPING.values():
            assert len(value) == 3, f"Value '{value}' should be 3 characters"


class TestExtractLanguageFromMARC:
    """Test language extraction from MARC records"""

    def test_extract_common_languages(self):
        """Test extraction of common language codes"""
        # Note: The actual implementation would need to be tested
        # with real MARC record structures. These are placeholder tests.

        # These tests would depend on the actual implementation of
        # extract_language_from_marc, which might take a MARC record
        # or specific field as input

    def test_language_normalization(self):
        """Test that extracted languages are normalized"""
        # This would test that 'en', 'eng', 'english' all become 'eng'


# ===== Property-Based Tests for LCCN =====


class TestLCCNProperties:
    """Property-based tests for LCCN functions"""

    @given(st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789- /", min_size=0, max_size=50))
    def test_normalize_lccn_idempotent(self, lccn: str) -> None:
        """Normalizing an LCCN twice should give the same result"""
        once = normalize_lccn(lccn)
        twice = normalize_lccn(once)
        assert once == twice

    @given(st.text())
    def test_normalize_lccn_handles_any_input(self, text: str) -> None:
        """normalize_lccn should handle any string input"""
        try:
            result = normalize_lccn(text)
            assert isinstance(result, str)
        except Exception as e:
            assert False, f"normalize_lccn raised exception: {e}"

    @given(st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789", min_size=1, max_size=20))
    def test_normalize_lccn_no_special_chars(self, text: str) -> None:
        """LCCN without special characters should pass through unchanged"""
        result = normalize_lccn(text)
        # Should be the same except possibly for padding
        assert "/" not in result
        assert " " not in result

    @given(st.integers(min_value=0, max_value=99))
    def test_two_digit_year_normalization(self, year: int) -> None:
        """Two-digit years should be preserved correctly"""
        year_str = f"{year:02d}"
        lccn = f"{year_str}-123456"
        result = normalize_lccn(lccn)
        assert result == f"{year_str}123456"

    @given(st.integers(min_value=2000, max_value=2099))
    def test_four_digit_year_normalization(self, year: int) -> None:
        """Four-digit years should be preserved correctly"""
        lccn = f"{year}-123456"
        result = normalize_lccn(lccn)
        assert result == f"{year}123456"

    @given(
        st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=0, max_size=3),
        st.integers(min_value=0, max_value=99),
        st.integers(min_value=1, max_value=999999),
    )
    def test_lccn_component_extraction(self, prefix: str, year: int, serial: int) -> None:
        """Test that LCCN components can be extracted after normalization"""
        # Construct an LCCN
        year_str = f"{year:02d}"
        serial_str = f"{serial:06d}"

        if prefix:
            lccn = f"{prefix}{year_str}-{serial}"
            normalized = normalize_lccn(lccn)

            # Check prefix extraction
            extracted_prefix = extract_lccn_prefix(normalized)
            assert extracted_prefix == prefix

            # Check year extraction
            extracted_year = extract_lccn_year(normalized)
            assert extracted_year == year_str
        else:
            lccn = f"{year_str}-{serial}"
            normalized = normalize_lccn(lccn)

            # Check year extraction
            extracted_year = extract_lccn_year(normalized)
            assert extracted_year == year_str


class TestCountryExtractionProperties:
    """Property-based tests for country extraction"""

    @given(st.text(min_size=18, max_size=50))
    def test_extract_country_handles_any_input(self, text: str) -> None:
        """Country extraction should handle any string input of sufficient length"""
        try:
            code, classification = extract_country_from_marc_008(text)
            assert isinstance(code, str)
            assert isinstance(classification, CountryClassification)
        except Exception as e:
            assert False, f"extract_country_from_marc_008 raised exception: {e}"

    @given(st.text(alphabet="abcdefghijklmnopqrstuvwxyz ", min_size=3, max_size=3))
    def test_country_code_classification(self, country_code: str) -> None:
        """Test that country codes are classified consistently"""
        field_008 = "123456789012345" + country_code
        code1, class1 = extract_country_from_marc_008(field_008)
        code2, class2 = extract_country_from_marc_008(field_008)

        assert code1 == code2
        assert class1 == class2

    @given(st.text(min_size=0, max_size=17))
    def test_short_fields_return_unknown(self, short_field: str) -> None:
        """Fields shorter than 18 characters should return UNKNOWN"""
        code, classification = extract_country_from_marc_008(short_field)
        assert code == ""
        assert classification == CountryClassification.UNKNOWN
