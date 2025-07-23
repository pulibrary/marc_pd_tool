# tests/test_utils/test_country_extraction.py

"""Tests for MARC country extraction functionality"""

# Third party imports

# Local imports
from marc_pd_tool.data.publication import CountryClassification
from marc_pd_tool.utils.marc_utilities import US_COUNTRY_CODES
from marc_pd_tool.utils.marc_utilities import extract_country_from_marc_008


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


class TestCountryExtractionEdgeCases:
    """Test edge cases and error conditions"""

    def test_none_input(self):
        """Test handling of None input"""
        # Note: This might cause a TypeError, but let's see what the actual behavior is
        try:
            code, classification = extract_country_from_marc_008(None)
            assert code == ""
            assert classification == CountryClassification.UNKNOWN
        except TypeError:
            # If it raises TypeError, that's also acceptable behavior
            pass

    def test_very_long_field_008(self):
        """Test handling of very long MARC 008 fields"""
        # Field with extra data beyond standard length
        long_field = "123456789012345xxu" + "x" * 100
        code, classification = extract_country_from_marc_008(long_field)

        assert code == "xxu"
        assert classification == CountryClassification.US

    def test_numeric_country_codes(self):
        """Test handling of numeric or mixed alphanumeric country codes"""
        test_cases = [
            ("123456789012345123", "123", CountryClassification.NON_US),
            ("12345678901234512a", "12a", CountryClassification.NON_US),
            ("123456789012345a1b", "a1b", CountryClassification.NON_US),
        ]

        for field_008, expected_code, expected_classification in test_cases:
            code, classification = extract_country_from_marc_008(field_008)
            assert code == expected_code, f"Expected code '{expected_code}', got '{code}'"
            assert (
                classification == expected_classification
            ), f"Expected {expected_classification}, got {classification}"

    def test_special_characters_in_country_code(self):
        """Test handling of special characters in country code positions"""
        test_cases = [
            ("123456789012345-xx", "-xx", CountryClassification.NON_US),
            ("123456789012345xx-", "xx-", CountryClassification.NON_US),
            ("123456789012345x.x", "x.x", CountryClassification.NON_US),
            ("123456789012345|||", "|||", CountryClassification.NON_US),
        ]

        for field_008, expected_code, expected_classification in test_cases:
            code, classification = extract_country_from_marc_008(field_008)
            assert code == expected_code, f"Expected code '{expected_code}', got '{code}'"
            assert (
                classification == expected_classification
            ), f"Expected {expected_classification}, got {classification}"

    def test_unicode_characters_in_field(self):
        """Test handling of Unicode characters in MARC 008 field"""
        test_cases = [
            ("123456789012345ñyu", "ñyu", CountryClassification.NON_US),
            ("123456789012345ëng", "ëng", CountryClassification.NON_US),
            ("123456789012345frê", "frê", CountryClassification.NON_US),
        ]

        for field_008, expected_code, expected_classification in test_cases:
            code, classification = extract_country_from_marc_008(field_008)
            assert code == expected_code, f"Expected code '{expected_code}', got '{code}'"
            assert (
                classification == expected_classification
            ), f"Expected {expected_classification}, got {classification}"


class TestCountryClassificationBoundaryConditions:
    """Test boundary conditions for country classification"""

    def test_all_us_codes_classified_correctly(self):
        """Test that all US country codes are classified as US"""
        for us_code in US_COUNTRY_CODES:
            field_008 = "123456789012345" + us_code
            code, classification = extract_country_from_marc_008(field_008)

            assert code == us_code, f"Expected code '{us_code}', got '{code}'"
            assert (
                classification == CountryClassification.US
            ), f"US code '{us_code}' not classified as US"

    def test_case_variations_of_us_codes(self):
        """Test that case variations of US codes are handled correctly"""
        test_us_codes = ["xxu", "nyu", "cau", "txu", "flu"]

        for base_code in test_us_codes:
            # Test uppercase
            upper_field = "123456789012345" + base_code.upper()
            code, classification = extract_country_from_marc_008(upper_field)
            assert (
                classification == CountryClassification.US
            ), f"Uppercase '{base_code.upper()}' not classified as US"

            # Test mixed case
            mixed_field = "123456789012345" + base_code.capitalize()
            code, classification = extract_country_from_marc_008(mixed_field)
            assert (
                classification == CountryClassification.US
            ), f"Mixed case '{base_code.capitalize()}' not classified as US"

    def test_non_us_codes_classification(self):
        """Test that various non-US codes are classified correctly"""
        non_us_codes = [
            "abc",
            "xyz",
            "123",
            "fr ",
            "enk",
            "gw ",
            "it ",
            "ja ",
            "au ",
            "ca ",
            "br ",
            "ru ",
            "ch ",
            "in ",
            "mx ",
            "uk ",
        ]

        for non_us_code in non_us_codes:
            # Skip if it happens to be a US code
            if non_us_code.strip().lower() in US_COUNTRY_CODES:
                continue

            field_008 = "123456789012345" + non_us_code
            code, classification = extract_country_from_marc_008(field_008)

            assert (
                classification == CountryClassification.NON_US
            ), f"Code '{non_us_code}' should be classified as NON_US"

    def test_empty_or_whitespace_codes(self):
        """Test that empty or whitespace-only codes return UNKNOWN"""
        whitespace_cases = [
            "123456789012345   ",  # Three spaces
            "123456789012345\t\t\t",  # Three tabs
            "123456789012345\n\n\n",  # Three newlines
            "123456789012345 \t ",  # Mixed whitespace
        ]

        for field_008 in whitespace_cases:
            code, classification = extract_country_from_marc_008(field_008)
            assert (
                code == "" or code.isspace()
            ), f"Expected empty/whitespace code for '{repr(field_008)}'"
            assert (
                classification == CountryClassification.UNKNOWN
            ), f"Expected UNKNOWN classification for whitespace code"


class TestReturnValueTypes:
    """Test that return values have correct types"""

    def test_return_tuple_structure(self):
        """Test that function returns a tuple with correct structure"""
        result = extract_country_from_marc_008("123456789012345xxu")

        assert isinstance(result, tuple), "Function should return a tuple"
        assert len(result) == 2, "Function should return a 2-tuple"

        code, classification = result
        assert isinstance(code, str), "Country code should be a string"
        assert isinstance(
            classification, CountryClassification
        ), "Classification should be CountryClassification enum"

    def test_country_classification_enum_values(self):
        """Test that all possible enum values can be returned"""
        # Test US classification
        code, classification = extract_country_from_marc_008("123456789012345xxu")
        assert classification == CountryClassification.US

        # Test NON_US classification
        code, classification = extract_country_from_marc_008("123456789012345enk")
        assert classification == CountryClassification.NON_US

        # Test UNKNOWN classification
        code, classification = extract_country_from_marc_008("123456789012345")
        assert classification == CountryClassification.UNKNOWN

    def test_string_code_properties(self):
        """Test properties of returned country code strings"""
        test_fields = [
            "123456789012345xxu",
            "123456789012345enk",
            "123456789012345",
            "123456789012345   ",
        ]

        for field in test_fields:
            code, classification = extract_country_from_marc_008(field)

            # Code should always be a string
            assert isinstance(code, str), f"Code should be string for field '{field}'"

            # Code should be at most 3 characters (could be empty or shorter)
            assert len(code) <= 3, f"Code should be at most 3 characters for field '{field}'"
