# tests/test_data/test_copyright_status_determination.py

"""Tests for copyright status determination algorithm"""

# Standard library imports
from datetime import datetime

# Local imports
from marc_pd_tool.data.enums import CopyrightStatus
from marc_pd_tool.data.enums import CopyrightStatusRule
from marc_pd_tool.data.enums import CountryClassification
from marc_pd_tool.data.publication import MatchResult
from marc_pd_tool.data.publication import Publication


class TestUSCopyrightStatusDetermination:
    """Test copyright status determination for US publications"""

    def test_us_pre_min_year_public_domain(self):
        """Test that US works published before min_year are public domain"""
        pub = Publication(
            title="Test Book",
            author="Test Author",
            pub_date="1920",  # Before default min_year of 1923
            country_classification=CountryClassification.US,
        )

        # Even with registration/renewal, pre-1928 is PD
        reg_match = MatchResult(
            matched_title="Test Book",
            matched_author="Test Author",
            similarity_score=90.0,
            title_score=95.0,
            author_score=85.0,
            year_difference=0,
            source_id="reg_001",
            source_type="registration",
        )
        pub.set_registration_match(reg_match)

        status = pub.determine_copyright_status()
        # Should return dynamic status like "US_PRE_1929"
        assert status.startswith("US_PRE_")
        assert pub.copyright_status == status
        assert pub.status_rule == CopyrightStatusRule.US_PRE_COPYRIGHT_EXPIRATION

    def test_us_1930_1963_no_renewal_rule(self):
        """Test special rule for US works 1930-1963 with registration but no renewal"""
        pub = Publication(
            title="Test Book",
            author="Test Author",
            pub_date="1955",
            country_classification=CountryClassification.US,
        )

        # Add registration match but no renewal
        reg_match = MatchResult(
            matched_title="Test Book",
            matched_author="Test Author",
            similarity_score=90.0,
            title_score=95.0,
            author_score=85.0,
            year_difference=0,
            source_id="reg_001",
            source_type="registration",
        )
        pub.set_registration_match(reg_match)

        status = pub.determine_copyright_status()
        assert status == CopyrightStatus.US_REGISTERED_NOT_RENEWED.value
        assert pub.copyright_status == CopyrightStatus.US_REGISTERED_NOT_RENEWED.value

    def test_us_1930_1963_with_renewal(self):
        """Test US works 1930-1963 that were renewed are still copyrighted"""
        pub = Publication(
            title="Test Book",
            author="Test Author",
            pub_date="1950",
            country_classification=CountryClassification.US,
        )

        # Add both registration and renewal matches
        reg_match = MatchResult(
            matched_title="Test Book",
            matched_author="Test Author",
            similarity_score=90.0,
            title_score=95.0,
            author_score=85.0,
            year_difference=0,
            source_id="reg_001",
            source_type="registration",
        )
        pub.set_registration_match(reg_match)

        ren_match = MatchResult(
            matched_title="Test Book",
            matched_author="Test Author",
            similarity_score=88.0,
            title_score=92.0,
            author_score=82.0,
            year_difference=0,
            source_id="ren_001",
            source_type="renewal",
        )
        pub.set_renewal_match(ren_match)

        status = pub.determine_copyright_status()
        assert status == CopyrightStatus.US_RENEWED.value
        assert pub.copyright_status == CopyrightStatus.US_RENEWED.value

    def test_us_1930_1963_no_registration_no_renewal(self):
        """Test US works 1930-1963 with no registration/renewal need verification"""
        pub = Publication(
            title="Test Book",
            author="Test Author",
            pub_date="1940",
            country_classification=CountryClassification.US,
        )

        # No matches added
        status = pub.determine_copyright_status()
        assert status == CopyrightStatus.US_NO_MATCH.value
        assert pub.copyright_status == CopyrightStatus.US_NO_MATCH.value

    def test_us_1930_1963_boundary_years(self):
        """Test boundary years for the 1930-1963 rule"""
        # Test 1930 (should use special rule)
        pub_1930 = Publication(
            title="Test Book 1930", pub_date="1930", country_classification=CountryClassification.US
        )
        reg_match = MatchResult(
            matched_title="Test Book 1930",
            matched_author="Test Author",
            similarity_score=90.0,
            title_score=95.0,
            author_score=85.0,
            year_difference=0,
            source_id="reg_001",
            source_type="registration",
        )
        pub_1930.set_registration_match(reg_match)
        assert (
            pub_1930.determine_copyright_status() == CopyrightStatus.US_REGISTERED_NOT_RENEWED.value
        )

        # Test 1963 (should use special rule)
        pub_1963 = Publication(
            title="Test Book 1963", pub_date="1963", country_classification=CountryClassification.US
        )
        pub_1963.set_registration_match(reg_match)
        assert (
            pub_1963.determine_copyright_status() == CopyrightStatus.US_REGISTERED_NOT_RENEWED.value
        )

        # Test 1929 (should use general rule)
        pub_1929 = Publication(
            title="Test Book 1929", pub_date="1929", country_classification=CountryClassification.US
        )
        pub_1929.set_registration_match(reg_match)
        # 1929 is exactly at the boundary (current_year - 96)
        # Standard library imports
        from datetime import datetime

        status = pub_1929.determine_copyright_status()
        # Could be either US_PRE_1929 or US_REGISTERED_NOT_RENEWED depending on current year
        assert status in [
            CopyrightStatus.US_REGISTERED_NOT_RENEWED.value,
            f"US_PRE_{datetime.now().year - 96}",
        ]

        # Test 1964 (should use general rule)
        pub_1964 = Publication(
            title="Test Book 1964", pub_date="1964", country_classification=CountryClassification.US
        )
        pub_1964.set_registration_match(reg_match)
        assert (
            pub_1964.determine_copyright_status() == CopyrightStatus.US_REGISTERED_NOT_RENEWED.value
        )

    def test_us_general_registration_no_renewal(self):
        """Test general US logic: registration but no renewal -> US_REGISTERED_NOT_RENEWED for 1978-1991"""
        pub = Publication(
            title="Test Book",
            author="Test Author",
            pub_date="1980",  # After 1977 (outside renewal period)
            country_classification=CountryClassification.US,
        )

        reg_match = MatchResult(
            matched_title="Test Book",
            matched_author="Test Author",
            similarity_score=90.0,
            title_score=95.0,
            author_score=85.0,
            year_difference=0,
            source_id="reg_001",
            source_type="registration",
        )
        pub.set_registration_match(reg_match)

        status = pub.determine_copyright_status()
        # 1980 is within our data range (up to 1991), should get normal status
        assert status == CopyrightStatus.US_REGISTERED_NOT_RENEWED.value

    def test_us_general_renewal_no_registration(self):
        """Test general US logic: renewal but no registration -> US_RENEWED for 1978-1991"""
        pub = Publication(
            title="Test Book",
            author="Test Author",
            pub_date="1980",  # After 1977 (outside renewal period)
            country_classification=CountryClassification.US,
        )

        ren_match = MatchResult(
            matched_title="Test Book",
            matched_author="Test Author",
            similarity_score=88.0,
            title_score=92.0,
            author_score=82.0,
            year_difference=0,
            source_id="ren_001",
            source_type="renewal",
        )
        pub.set_renewal_match(ren_match)

        status = pub.determine_copyright_status()
        # 1980 is within our data range (up to 1991), renewal found = renewed
        assert status == CopyrightStatus.US_RENEWED.value

    def test_us_general_no_registration_no_renewal(self):
        """Test general US logic: no registration and no renewal -> US_NO_MATCH for 1978-1991"""
        pub = Publication(
            title="Test Book",
            author="Test Author",
            pub_date="1985",  # After 1977 (outside renewal period)
            country_classification=CountryClassification.US,
        )

        # No matches added
        status = pub.determine_copyright_status()
        # 1985 is within our data range (up to 1991), should get normal status
        assert status == CopyrightStatus.US_NO_MATCH.value

    def test_us_general_both_registration_and_renewal(self):
        """Test general US logic: both registration and renewal -> US_RENEWED"""
        pub = Publication(
            title="Test Book",
            author="Test Author",
            pub_date="1980",
            country_classification=CountryClassification.US,
        )

        # Add both matches
        reg_match = MatchResult(
            matched_title="Test Book",
            matched_author="Test Author",
            similarity_score=90.0,
            title_score=95.0,
            author_score=85.0,
            year_difference=0,
            source_id="reg_001",
            source_type="registration",
        )
        pub.set_registration_match(reg_match)

        ren_match = MatchResult(
            matched_title="Test Book",
            matched_author="Test Author",
            similarity_score=88.0,
            title_score=92.0,
            author_score=82.0,
            year_difference=0,
            source_id="ren_001",
            source_type="renewal",
        )
        pub.set_renewal_match(ren_match)

        status = pub.determine_copyright_status()
        # 1980 is within our data range (up to 1991), renewal found = renewed
        assert status == CopyrightStatus.US_RENEWED.value


class TestNonUSCopyrightStatusDetermination:
    """Test copyright status determination for Non-US publications"""

    def test_non_us_with_registration_match(self):
        """Test Non-US record with registration match -> FOREIGN_REGISTERED_NOT_RENEWED_{COUNTRY}"""
        pub = Publication(
            title="Test Book",
            author="Test Author",
            pub_date="1950",
            country_classification=CountryClassification.NON_US,
            country_code="GBR",  # Add country code for testing
        )

        reg_match = MatchResult(
            matched_title="Test Book",
            matched_author="Test Author",
            similarity_score=90.0,
            title_score=95.0,
            author_score=85.0,
            year_difference=0,
            source_id="reg_001",
            source_type="registration",
        )
        pub.set_registration_match(reg_match)

        status = pub.determine_copyright_status()
        # Foreign work with registration should have country code appended
        assert status == f"{CopyrightStatus.FOREIGN_REGISTERED_NOT_RENEWED.value}_GBR"

    def test_non_us_with_renewal_match(self):
        """Test Non-US record with renewal match -> FOREIGN_RENEWED_{COUNTRY}"""
        pub = Publication(
            title="Test Book",
            author="Test Author",
            pub_date="1960",
            country_classification=CountryClassification.NON_US,
            country_code="FRA",  # Add country code for testing
        )

        ren_match = MatchResult(
            matched_title="Test Book",
            matched_author="Test Author",
            similarity_score=88.0,
            title_score=92.0,
            author_score=82.0,
            year_difference=0,
            source_id="ren_001",
            source_type="renewal",
        )
        pub.set_renewal_match(ren_match)

        status = pub.determine_copyright_status()
        # Foreign work with renewal should have country code appended
        assert status == f"{CopyrightStatus.FOREIGN_RENEWED.value}_FRA"

    def test_non_us_with_both_matches(self):
        """Test Non-US record with both matches -> FOREIGN_RENEWED_{COUNTRY}"""
        pub = Publication(
            title="Test Book",
            author="Test Author",
            pub_date="1955",
            country_classification=CountryClassification.NON_US,
            country_code="DEU",  # Add country code for testing
        )

        # Add both matches
        reg_match = MatchResult(
            matched_title="Test Book",
            matched_author="Test Author",
            similarity_score=90.0,
            title_score=95.0,
            author_score=85.0,
            year_difference=0,
            source_id="reg_001",
            source_type="registration",
        )
        pub.set_registration_match(reg_match)

        ren_match = MatchResult(
            matched_title="Test Book",
            matched_author="Test Author",
            similarity_score=88.0,
            title_score=92.0,
            author_score=82.0,
            year_difference=0,
            source_id="ren_001",
            source_type="renewal",
        )
        pub.set_renewal_match(ren_match)

        status = pub.determine_copyright_status()
        # Foreign work with renewal takes precedence
        assert status == f"{CopyrightStatus.FOREIGN_RENEWED.value}_DEU"

    def test_non_us_no_matches(self):
        """Test Non-US record with no matches -> FOREIGN_NO_MATCH_{COUNTRY}"""
        pub = Publication(
            title="Test Book",
            author="Test Author",
            pub_date="1945",
            country_classification=CountryClassification.NON_US,
            country_code="ITA",  # Add country code for testing
        )

        # No matches added
        status = pub.determine_copyright_status()
        assert status == f"{CopyrightStatus.FOREIGN_NO_MATCH.value}_ITA"


class TestUnknownCountryCopyrightStatusDetermination:
    """Test copyright status determination for unknown country publications"""

    def test_unknown_country_with_matches(self):
        """Test unknown country record with matches -> COUNTRY_UNKNOWN"""
        pub = Publication(
            title="Test Book",
            author="Test Author",
            pub_date="1950",
            country_classification=CountryClassification.UNKNOWN,
        )

        reg_match = MatchResult(
            matched_title="Test Book",
            matched_author="Test Author",
            similarity_score=90.0,
            title_score=95.0,
            author_score=85.0,
            year_difference=0,
            source_id="reg_001",
            source_type="registration",
        )
        pub.set_registration_match(reg_match)

        status = pub.determine_copyright_status()
        assert status == CopyrightStatus.COUNTRY_UNKNOWN_REGISTERED_NOT_RENEWED.value

    def test_unknown_country_no_matches(self):
        """Test unknown country record with no matches -> COUNTRY_UNKNOWN_NO_MATCH"""
        pub = Publication(
            title="Test Book",
            author="Test Author",
            pub_date="1950",
            country_classification=CountryClassification.UNKNOWN,
        )

        # No matches added
        status = pub.determine_copyright_status()
        assert status == CopyrightStatus.COUNTRY_UNKNOWN_NO_MATCH.value


class TestCopyrightStatusEdgeCases:
    """Test edge cases and special scenarios for copyright status determination"""

    def test_no_year_information(self):
        """Test publications without year information"""
        pub = Publication(
            title="Test Book",
            author="Test Author",
            pub_date="",  # No date
            country_classification=CountryClassification.US,
        )

        reg_match = MatchResult(
            matched_title="Test Book",
            matched_author="Test Author",
            similarity_score=90.0,
            title_score=95.0,
            author_score=85.0,
            year_difference=0,
            source_id="reg_001",
            source_type="registration",
        )
        pub.set_registration_match(reg_match)

        # Should use general US logic since year is None
        status = pub.determine_copyright_status()
        assert status == CopyrightStatus.US_REGISTERED_NOT_RENEWED.value

    def test_invalid_year_information(self):
        """Test publications with invalid year information"""
        pub = Publication(
            title="Test Book",
            author="Test Author",
            pub_date="Ancient times",  # Invalid date
            country_classification=CountryClassification.US,
        )

        reg_match = MatchResult(
            matched_title="Test Book",
            matched_author="Test Author",
            similarity_score=90.0,
            title_score=95.0,
            author_score=85.0,
            year_difference=0,
            source_id="reg_001",
            source_type="registration",
        )
        pub.set_registration_match(reg_match)

        # Should use general US logic since year extraction failed
        status = pub.determine_copyright_status()
        assert status == CopyrightStatus.US_REGISTERED_NOT_RENEWED.value

    def test_multiple_status_determination_calls(self):
        """Test that multiple calls to determine_copyright_status are consistent"""
        pub = Publication(
            title="Test Book",
            author="Test Author",
            pub_date="1955",
            country_classification=CountryClassification.US,
        )

        reg_match = MatchResult(
            matched_title="Test Book",
            matched_author="Test Author",
            similarity_score=90.0,
            title_score=95.0,
            author_score=85.0,
            year_difference=0,
            source_id="reg_001",
            source_type="registration",
        )
        pub.set_registration_match(reg_match)

        # Call multiple times and ensure consistent results
        status1 = pub.determine_copyright_status()
        status2 = pub.determine_copyright_status()
        status3 = pub.determine_copyright_status()

        assert status1 == status2 == status3 == CopyrightStatus.US_REGISTERED_NOT_RENEWED.value
        assert pub.copyright_status == CopyrightStatus.US_REGISTERED_NOT_RENEWED.value

    def test_status_updates_when_matches_change(self):
        """Test that status updates when matches are added after initial determination"""
        pub = Publication(
            title="Test Book",
            author="Test Author",
            pub_date="1955",
            country_classification=CountryClassification.US,
        )

        # Initially no matches
        status1 = pub.determine_copyright_status()
        assert status1 == CopyrightStatus.US_NO_MATCH.value

        # Add registration match
        reg_match = MatchResult(
            matched_title="Test Book",
            matched_author="Test Author",
            similarity_score=90.0,
            title_score=95.0,
            author_score=85.0,
            year_difference=0,
            source_id="reg_001",
            source_type="registration",
        )
        pub.set_registration_match(reg_match)

        status2 = pub.determine_copyright_status()
        assert status2 == CopyrightStatus.US_REGISTERED_NOT_RENEWED.value

        # Add renewal match
        ren_match = MatchResult(
            matched_title="Test Book",
            matched_author="Test Author",
            similarity_score=88.0,
            title_score=92.0,
            author_score=82.0,
            year_difference=0,
            source_id="ren_001",
            source_type="renewal",
        )
        pub.set_renewal_match(ren_match)

        status3 = pub.determine_copyright_status()
        assert status3 == CopyrightStatus.US_RENEWED.value
