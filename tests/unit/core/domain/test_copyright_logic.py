# tests/unit/core/domain/test_copyright_logic.py

"""Comprehensive tests for copyright_logic module"""

# Standard library imports
from datetime import datetime

# Local imports
from marc_pd_tool.core.domain.copyright_logic import determine_copyright_status
from marc_pd_tool.core.domain.enums import CopyrightStatus
from marc_pd_tool.core.domain.enums import CopyrightStatusRule
from marc_pd_tool.core.domain.enums import CountryClassification
from marc_pd_tool.core.domain.match_result import MatchResult
from marc_pd_tool.core.domain.publication import Publication


class TestCopyrightStatusDetermination:
    """Test copyright status determination logic"""

    def test_default_copyright_expiration_year(self) -> None:
        """Test that default copyright expiration year is calculated correctly"""
        pub = Publication("Test", pub_date="1925", country_classification=CountryClassification.US)
        status = determine_copyright_status(pub)

        expected_year = datetime.now().year - 96
        assert status == f"US_PRE_{expected_year}"
        assert pub.status_rule == CopyrightStatusRule.US_PRE_COPYRIGHT_EXPIRATION

    def test_default_max_data_year(self) -> None:
        """Test that default max data year is set to 1991"""
        pub = Publication("Test", pub_date="1995", country_classification=CountryClassification.US)
        status = determine_copyright_status(pub)

        assert status == "OUT_OF_DATA_RANGE_1991"
        assert pub.status_rule == CopyrightStatusRule.OUT_OF_DATA_RANGE

    def test_us_pre_copyright_expiration(self) -> None:
        """Test US works before copyright expiration year"""
        pub = Publication("Test", pub_date="1920", country_classification=CountryClassification.US)
        status = determine_copyright_status(pub, copyright_expiration_year=1929)

        assert status == "US_PRE_1929"
        assert pub.copyright_status == "US_PRE_1929"
        assert pub.status_rule == CopyrightStatusRule.US_PRE_COPYRIGHT_EXPIRATION

    def test_non_us_pre_copyright_expiration_with_country_code(self) -> None:
        """Test NON_US works before copyright expiration with country code"""
        pub = Publication(
            "Test",
            pub_date="1920",
            country_classification=CountryClassification.NON_US,
            country_code="gbr",
        )
        status = determine_copyright_status(pub, copyright_expiration_year=1929)

        assert status == "FOREIGN_PRE_1929_gbr"
        assert pub.copyright_status == "FOREIGN_PRE_1929_gbr"
        assert pub.status_rule == CopyrightStatusRule.FOREIGN_PRE_COPYRIGHT_EXPIRATION

    def test_non_us_pre_copyright_expiration_without_country_code(self) -> None:
        """Test NON_US works before copyright expiration without country code"""
        pub = Publication(
            "Test", pub_date="1920", country_classification=CountryClassification.NON_US
        )
        status = determine_copyright_status(pub, copyright_expiration_year=1929)

        assert status == "FOREIGN_PRE_1929"
        assert pub.copyright_status == "FOREIGN_PRE_1929"
        assert pub.status_rule == CopyrightStatusRule.FOREIGN_PRE_COPYRIGHT_EXPIRATION

    def test_unknown_country_pre_copyright_expiration(self) -> None:
        """Test UNKNOWN country works before copyright expiration"""
        pub = Publication(
            "Test", pub_date="1920", country_classification=CountryClassification.UNKNOWN
        )
        status = determine_copyright_status(pub, copyright_expiration_year=1929)

        assert status == "COUNTRY_UNKNOWN_PRE_1929"
        assert pub.copyright_status == "COUNTRY_UNKNOWN_PRE_1929"
        assert pub.status_rule == CopyrightStatusRule.US_PRE_COPYRIGHT_EXPIRATION

    def test_out_of_data_range(self) -> None:
        """Test works beyond max data year"""
        pub = Publication("Test", pub_date="1995", country_classification=CountryClassification.US)
        status = determine_copyright_status(pub, max_data_year=1991)

        assert status == "OUT_OF_DATA_RANGE_1991"
        assert pub.copyright_status == "OUT_OF_DATA_RANGE_1991"
        assert pub.status_rule == CopyrightStatusRule.OUT_OF_DATA_RANGE

    def test_us_renewal_period_registered_not_renewed(self) -> None:
        """Test US works in renewal period (1929-1977) with registration but no renewal"""
        pub = Publication("Test", pub_date="1950", country_classification=CountryClassification.US)
        pub.registration_match = MatchResult(
            matched_title="Test",
            matched_author="Author",
            similarity_score=90.0,
            title_score=90.0,
            author_score=90.0,
            year_difference=0,
            source_id="reg_001",
            source_type="registration",
        )

        status = determine_copyright_status(pub, copyright_expiration_year=1929)

        assert status == CopyrightStatus.US_REGISTERED_NOT_RENEWED.value
        assert pub.status_rule == CopyrightStatusRule.US_RENEWAL_PERIOD_NOT_RENEWED

    def test_us_renewal_period_renewed(self) -> None:
        """Test US works in renewal period with renewal"""
        pub = Publication("Test", pub_date="1950", country_classification=CountryClassification.US)
        pub.renewal_match = MatchResult(
            matched_title="Test",
            matched_author="Author",
            similarity_score=90.0,
            title_score=90.0,
            author_score=90.0,
            year_difference=0,
            source_id="ren_001",
            source_type="renewal",
        )

        status = determine_copyright_status(pub, copyright_expiration_year=1929)

        assert status == CopyrightStatus.US_RENEWED.value
        assert pub.status_rule == CopyrightStatusRule.US_RENEWAL_PERIOD_RENEWED

    def test_us_renewal_period_no_match(self) -> None:
        """Test US works in renewal period with no matches"""
        pub = Publication("Test", pub_date="1950", country_classification=CountryClassification.US)

        status = determine_copyright_status(pub, copyright_expiration_year=1929)

        assert status == CopyrightStatus.US_NO_MATCH.value
        assert pub.status_rule == CopyrightStatusRule.US_RENEWAL_PERIOD_NO_MATCH

    def test_us_no_year_registered_not_renewed(self) -> None:
        """Test US works without year that have registration but no renewal"""
        pub = Publication("Test", country_classification=CountryClassification.US)
        pub.registration_match = MatchResult(
            matched_title="Test",
            matched_author="Author",
            similarity_score=90.0,
            title_score=90.0,
            author_score=90.0,
            year_difference=0,
            source_id="reg_001",
            source_type="registration",
        )

        status = determine_copyright_status(pub, copyright_expiration_year=1929)

        assert status == CopyrightStatus.US_REGISTERED_NOT_RENEWED.value
        assert pub.status_rule == CopyrightStatusRule.US_REGISTERED_NO_RENEWAL

    def test_us_no_year_renewal_only(self) -> None:
        """Test US works without year that have renewal only"""
        pub = Publication("Test", country_classification=CountryClassification.US)
        pub.renewal_match = MatchResult(
            matched_title="Test",
            matched_author="Author",
            similarity_score=90.0,
            title_score=90.0,
            author_score=90.0,
            year_difference=0,
            source_id="ren_001",
            source_type="renewal",
        )

        status = determine_copyright_status(pub, copyright_expiration_year=1929)

        assert status == CopyrightStatus.US_RENEWED.value
        assert pub.status_rule == CopyrightStatusRule.US_RENEWAL_FOUND

    def test_us_no_year_both_registration_and_renewal(self) -> None:
        """Test US works without year that have both registration and renewal"""
        pub = Publication("Test", country_classification=CountryClassification.US)
        pub.registration_match = MatchResult(
            matched_title="Test",
            matched_author="Author",
            similarity_score=90.0,
            title_score=90.0,
            author_score=90.0,
            year_difference=0,
            source_id="reg_001",
            source_type="registration",
        )
        pub.renewal_match = MatchResult(
            matched_title="Test",
            matched_author="Author",
            similarity_score=90.0,
            title_score=90.0,
            author_score=90.0,
            year_difference=0,
            source_id="ren_001",
            source_type="renewal",
        )

        status = determine_copyright_status(pub, copyright_expiration_year=1929)

        assert status == CopyrightStatus.US_RENEWED.value
        assert pub.status_rule == CopyrightStatusRule.US_BOTH_REG_AND_RENEWAL

    def test_us_no_year_no_matches(self) -> None:
        """Test US works without year and no matches"""
        pub = Publication("Test", country_classification=CountryClassification.US)

        status = determine_copyright_status(pub, copyright_expiration_year=1929)

        assert status == CopyrightStatus.US_NO_MATCH.value
        assert pub.status_rule == CopyrightStatusRule.US_NO_MATCH

    def test_us_outside_renewal_period_registered_not_renewed(self) -> None:
        """Test US works after 1977 with registration but no renewal"""
        pub = Publication("Test", pub_date="1980", country_classification=CountryClassification.US)
        pub.registration_match = MatchResult(
            matched_title="Test",
            matched_author="Author",
            similarity_score=90.0,
            title_score=90.0,
            author_score=90.0,
            year_difference=0,
            source_id="reg_001",
            source_type="registration",
        )

        status = determine_copyright_status(pub, copyright_expiration_year=1929, max_data_year=1991)

        assert status == CopyrightStatus.US_REGISTERED_NOT_RENEWED.value
        assert pub.status_rule == CopyrightStatusRule.US_REGISTERED_NO_RENEWAL

    def test_foreign_renewed_with_country_code(self) -> None:
        """Test foreign works with renewal and country code"""
        pub = Publication(
            "Test",
            pub_date="1950",
            country_classification=CountryClassification.NON_US,
            country_code="gbr",
        )
        pub.renewal_match = MatchResult(
            matched_title="Test",
            matched_author="Author",
            similarity_score=90.0,
            title_score=90.0,
            author_score=90.0,
            year_difference=0,
            source_id="ren_001",
            source_type="renewal",
        )

        status = determine_copyright_status(pub, copyright_expiration_year=1929)

        assert status == f"{CopyrightStatus.FOREIGN_RENEWED.value}_gbr"
        assert pub.status_rule == CopyrightStatusRule.FOREIGN_RENEWED

    def test_foreign_renewed_without_country_code(self) -> None:
        """Test foreign works with renewal but no country code"""
        pub = Publication(
            "Test", pub_date="1950", country_classification=CountryClassification.NON_US
        )
        pub.renewal_match = MatchResult(
            matched_title="Test",
            matched_author="Author",
            similarity_score=90.0,
            title_score=90.0,
            author_score=90.0,
            year_difference=0,
            source_id="ren_001",
            source_type="renewal",
        )

        status = determine_copyright_status(pub, copyright_expiration_year=1929)

        assert status == CopyrightStatus.FOREIGN_RENEWED.value
        assert pub.status_rule == CopyrightStatusRule.FOREIGN_RENEWED

    def test_foreign_registered_not_renewed_with_country_code(self) -> None:
        """Test foreign works with registration but no renewal and country code"""
        pub = Publication(
            "Test",
            pub_date="1950",
            country_classification=CountryClassification.NON_US,
            country_code="fra",
        )
        pub.registration_match = MatchResult(
            matched_title="Test",
            matched_author="Author",
            similarity_score=90.0,
            title_score=90.0,
            author_score=90.0,
            year_difference=0,
            source_id="reg_001",
            source_type="registration",
        )

        status = determine_copyright_status(pub, copyright_expiration_year=1929)

        assert status == f"{CopyrightStatus.FOREIGN_REGISTERED_NOT_RENEWED.value}_fra"
        assert pub.status_rule == CopyrightStatusRule.FOREIGN_REGISTERED_NOT_RENEWED

    def test_foreign_registered_not_renewed_without_country_code(self) -> None:
        """Test foreign works with registration but no renewal and no country code"""
        pub = Publication(
            "Test", pub_date="1950", country_classification=CountryClassification.NON_US
        )
        pub.registration_match = MatchResult(
            matched_title="Test",
            matched_author="Author",
            similarity_score=90.0,
            title_score=90.0,
            author_score=90.0,
            year_difference=0,
            source_id="reg_001",
            source_type="registration",
        )

        status = determine_copyright_status(pub, copyright_expiration_year=1929)

        assert status == CopyrightStatus.FOREIGN_REGISTERED_NOT_RENEWED.value
        assert pub.status_rule == CopyrightStatusRule.FOREIGN_REGISTERED_NOT_RENEWED

    def test_foreign_no_match_with_country_code(self) -> None:
        """Test foreign works with no matches and country code"""
        pub = Publication(
            "Test",
            pub_date="1950",
            country_classification=CountryClassification.NON_US,
            country_code="deu",
        )

        status = determine_copyright_status(pub, copyright_expiration_year=1929)

        assert status == f"{CopyrightStatus.FOREIGN_NO_MATCH.value}_deu"
        assert pub.status_rule == CopyrightStatusRule.FOREIGN_NO_MATCH

    def test_foreign_no_match_without_country_code(self) -> None:
        """Test foreign works with no matches and no country code"""
        pub = Publication(
            "Test", pub_date="1950", country_classification=CountryClassification.NON_US
        )

        status = determine_copyright_status(pub, copyright_expiration_year=1929)

        assert status == CopyrightStatus.FOREIGN_NO_MATCH.value
        assert pub.status_rule == CopyrightStatusRule.FOREIGN_NO_MATCH

    def test_unknown_country_renewed(self) -> None:
        """Test unknown country with renewal"""
        pub = Publication(
            "Test", pub_date="1950", country_classification=CountryClassification.UNKNOWN
        )
        pub.renewal_match = MatchResult(
            matched_title="Test",
            matched_author="Author",
            similarity_score=90.0,
            title_score=90.0,
            author_score=90.0,
            year_difference=0,
            source_id="ren_001",
            source_type="renewal",
        )

        status = determine_copyright_status(pub, copyright_expiration_year=1929)

        assert status == CopyrightStatus.COUNTRY_UNKNOWN_RENEWED.value
        assert pub.status_rule == CopyrightStatusRule.COUNTRY_UNKNOWN_RENEWED

    def test_unknown_country_registered_not_renewed(self) -> None:
        """Test unknown country with registration but no renewal"""
        pub = Publication(
            "Test", pub_date="1950", country_classification=CountryClassification.UNKNOWN
        )
        pub.registration_match = MatchResult(
            matched_title="Test",
            matched_author="Author",
            similarity_score=90.0,
            title_score=90.0,
            author_score=90.0,
            year_difference=0,
            source_id="reg_001",
            source_type="registration",
        )

        status = determine_copyright_status(pub, copyright_expiration_year=1929)

        assert status == CopyrightStatus.COUNTRY_UNKNOWN_REGISTERED_NOT_RENEWED.value
        assert pub.status_rule == CopyrightStatusRule.COUNTRY_UNKNOWN_REGISTERED

    def test_unknown_country_no_match(self) -> None:
        """Test unknown country with no matches"""
        pub = Publication(
            "Test", pub_date="1950", country_classification=CountryClassification.UNKNOWN
        )

        status = determine_copyright_status(pub, copyright_expiration_year=1929)

        assert status == CopyrightStatus.COUNTRY_UNKNOWN_NO_MATCH.value
        assert pub.status_rule == CopyrightStatusRule.COUNTRY_UNKNOWN_NO_MATCH

    def test_edge_case_renewal_period_boundary_lower(self) -> None:
        """Test edge case at lower boundary of renewal period"""
        pub = Publication("Test", pub_date="1929", country_classification=CountryClassification.US)
        pub.registration_match = MatchResult(
            matched_title="Test",
            matched_author="Author",
            similarity_score=90.0,
            title_score=90.0,
            author_score=90.0,
            year_difference=0,
            source_id="reg_001",
            source_type="registration",
        )

        status = determine_copyright_status(pub, copyright_expiration_year=1929)

        assert status == CopyrightStatus.US_REGISTERED_NOT_RENEWED.value
        assert pub.status_rule == CopyrightStatusRule.US_RENEWAL_PERIOD_NOT_RENEWED

    def test_edge_case_renewal_period_boundary_upper(self) -> None:
        """Test edge case at upper boundary of renewal period"""
        pub = Publication("Test", pub_date="1977", country_classification=CountryClassification.US)
        pub.renewal_match = MatchResult(
            matched_title="Test",
            matched_author="Author",
            similarity_score=90.0,
            title_score=90.0,
            author_score=90.0,
            year_difference=0,
            source_id="ren_001",
            source_type="renewal",
        )

        status = determine_copyright_status(pub, copyright_expiration_year=1929)

        assert status == CopyrightStatus.US_RENEWED.value
        assert pub.status_rule == CopyrightStatusRule.US_RENEWAL_PERIOD_RENEWED

    def test_edge_case_just_after_renewal_period(self) -> None:
        """Test edge case just after renewal period"""
        pub = Publication("Test", pub_date="1978", country_classification=CountryClassification.US)
        pub.registration_match = MatchResult(
            matched_title="Test",
            matched_author="Author",
            similarity_score=90.0,
            title_score=90.0,
            author_score=90.0,
            year_difference=0,
            source_id="reg_001",
            source_type="registration",
        )

        status = determine_copyright_status(pub, copyright_expiration_year=1929, max_data_year=1991)

        assert status == CopyrightStatus.US_REGISTERED_NOT_RENEWED.value
        assert pub.status_rule == CopyrightStatusRule.US_REGISTERED_NO_RENEWAL

    def test_foreign_with_both_matches_prefers_renewal(self) -> None:
        """Test that foreign works with both matches prefer renewal status"""
        pub = Publication(
            "Test",
            pub_date="1950",
            country_classification=CountryClassification.NON_US,
            country_code="gbr",
        )
        pub.registration_match = MatchResult(
            matched_title="Test",
            matched_author="Author",
            similarity_score=85.0,
            title_score=85.0,
            author_score=85.0,
            year_difference=0,
            source_id="reg_001",
            source_type="registration",
        )
        pub.renewal_match = MatchResult(
            matched_title="Test",
            matched_author="Author",
            similarity_score=90.0,
            title_score=90.0,
            author_score=90.0,
            year_difference=0,
            source_id="ren_001",
            source_type="renewal",
        )

        status = determine_copyright_status(pub, copyright_expiration_year=1929)

        # Renewal takes precedence
        assert status == f"{CopyrightStatus.FOREIGN_RENEWED.value}_gbr"
        assert pub.status_rule == CopyrightStatusRule.FOREIGN_RENEWED

    def test_country_unknown_no_match(self) -> None:
        """Test country unknown with no registration or renewal matches (line 124)"""
        pub = Publication(
            "Test", pub_date="1950", country_classification=CountryClassification.UNKNOWN
        )
        # No registration or renewal matches

        status = determine_copyright_status(pub, copyright_expiration_year=1929)

        assert status == CopyrightStatus.COUNTRY_UNKNOWN_NO_MATCH.value
        assert pub.status_rule == CopyrightStatusRule.COUNTRY_UNKNOWN_NO_MATCH

    def test_return_value_matches_publication_status(self) -> None:
        """Test that the return value matches what's set on the publication"""
        pub = Publication("Test", pub_date="1950", country_classification=CountryClassification.US)

        status = determine_copyright_status(pub, copyright_expiration_year=1929)

        # Verify return value matches what was set on publication
        assert status == pub.copyright_status
        assert status == CopyrightStatus.US_NO_MATCH.value
