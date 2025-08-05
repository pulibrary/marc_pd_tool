# tests/test_data/test_copyright_status_determination.py

"""Tests for copyright status determination algorithm"""

# Third party imports

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
        assert status == CopyrightStatus.PD_PRE_MIN_YEAR
        assert pub.copyright_status == CopyrightStatus.PD_PRE_MIN_YEAR
        assert pub.status_rule == CopyrightStatusRule.US_PRE_MIN_YEAR

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
        assert status == CopyrightStatus.PD_US_NOT_RENEWED
        assert pub.copyright_status == CopyrightStatus.PD_US_NOT_RENEWED

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
        assert status == CopyrightStatus.IN_COPYRIGHT_US_RENEWED
        assert pub.copyright_status == CopyrightStatus.IN_COPYRIGHT_US_RENEWED

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
        assert status == CopyrightStatus.UNKNOWN_US_NO_DATA
        assert pub.copyright_status == CopyrightStatus.UNKNOWN_US_NO_DATA

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
        assert pub_1930.determine_copyright_status() == CopyrightStatus.PD_US_NOT_RENEWED

        # Test 1963 (should use special rule)
        pub_1963 = Publication(
            title="Test Book 1963", pub_date="1963", country_classification=CountryClassification.US
        )
        pub_1963.set_registration_match(reg_match)
        assert pub_1963.determine_copyright_status() == CopyrightStatus.PD_US_NOT_RENEWED

        # Test 1929 (should use general rule)
        pub_1929 = Publication(
            title="Test Book 1929", pub_date="1929", country_classification=CountryClassification.US
        )
        pub_1929.set_registration_match(reg_match)
        assert pub_1929.determine_copyright_status() == CopyrightStatus.PD_US_NOT_RENEWED

        # Test 1964 (should use general rule)
        pub_1964 = Publication(
            title="Test Book 1964", pub_date="1964", country_classification=CountryClassification.US
        )
        pub_1964.set_registration_match(reg_match)
        assert pub_1964.determine_copyright_status() == CopyrightStatus.PD_US_NOT_RENEWED

    def test_us_general_registration_no_renewal(self):
        """Test general US logic: registration but no renewal -> PD_US_REG_NO_RENEWAL"""
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
        assert status == CopyrightStatus.PD_US_REG_NO_RENEWAL

    def test_us_general_renewal_no_registration(self):
        """Test general US logic: renewal but no registration -> IN_COPYRIGHT"""
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
        assert status == CopyrightStatus.IN_COPYRIGHT

    def test_us_general_no_registration_no_renewal(self):
        """Test general US logic: no registration and no renewal -> PD_US_NO_REG_DATA"""
        pub = Publication(
            title="Test Book",
            author="Test Author",
            pub_date="1985",  # After 1977 (outside renewal period)
            country_classification=CountryClassification.US,
        )

        # No matches added
        status = pub.determine_copyright_status()
        assert status == CopyrightStatus.PD_US_NO_REG_DATA

    def test_us_general_both_registration_and_renewal(self):
        """Test general US logic: both registration and renewal -> IN_COPYRIGHT"""
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
        assert status == CopyrightStatus.IN_COPYRIGHT


class TestNonUSCopyrightStatusDetermination:
    """Test copyright status determination for Non-US publications"""

    def test_non_us_with_registration_match(self):
        """Test Non-US record with registration match -> RESEARCH_US_STATUS"""
        pub = Publication(
            title="Test Book",
            author="Test Author",
            pub_date="1950",
            country_classification=CountryClassification.NON_US,
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
        assert status == CopyrightStatus.RESEARCH_US_STATUS

    def test_non_us_with_renewal_match(self):
        """Test Non-US record with renewal match -> RESEARCH_US_STATUS"""
        pub = Publication(
            title="Test Book",
            author="Test Author",
            pub_date="1960",
            country_classification=CountryClassification.NON_US,
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
        assert status == CopyrightStatus.RESEARCH_US_STATUS

    def test_non_us_with_both_matches(self):
        """Test Non-US record with both matches -> RESEARCH_US_STATUS"""
        pub = Publication(
            title="Test Book",
            author="Test Author",
            pub_date="1955",
            country_classification=CountryClassification.NON_US,
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
        assert status == CopyrightStatus.RESEARCH_US_STATUS

    def test_non_us_no_matches(self):
        """Test Non-US record with no matches -> RESEARCH_US_ONLY_PD"""
        pub = Publication(
            title="Test Book",
            author="Test Author",
            pub_date="1945",
            country_classification=CountryClassification.NON_US,
        )

        # No matches added
        status = pub.determine_copyright_status()
        assert status == CopyrightStatus.RESEARCH_US_ONLY_PD


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
        assert status == CopyrightStatus.COUNTRY_UNKNOWN

    def test_unknown_country_no_matches(self):
        """Test unknown country record with no matches -> COUNTRY_UNKNOWN"""
        pub = Publication(
            title="Test Book",
            author="Test Author",
            pub_date="1950",
            country_classification=CountryClassification.UNKNOWN,
        )

        # No matches added
        status = pub.determine_copyright_status()
        assert status == CopyrightStatus.COUNTRY_UNKNOWN


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
        assert status == CopyrightStatus.PD_US_REG_NO_RENEWAL

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
        assert status == CopyrightStatus.PD_US_REG_NO_RENEWAL

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

        assert status1 == status2 == status3 == CopyrightStatus.PD_US_NOT_RENEWED
        assert pub.copyright_status == CopyrightStatus.PD_US_NOT_RENEWED

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
        assert status1 == CopyrightStatus.UNKNOWN_US_NO_DATA

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
        assert status2 == CopyrightStatus.PD_US_NOT_RENEWED

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
        assert status3 == CopyrightStatus.IN_COPYRIGHT_US_RENEWED
