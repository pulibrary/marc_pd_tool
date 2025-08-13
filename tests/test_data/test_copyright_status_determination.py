# tests/test_data/test_copyright_status_determination.py

"""Basic sanity tests for copyright status determination

For comprehensive property-based testing of all combinations,
see test_copyright_status_hypothesis.py
"""

# Standard library imports
from datetime import datetime

# Local imports
from marc_pd_tool.core.domain.enums import CopyrightStatus
from marc_pd_tool.core.domain.enums import CopyrightStatusRule
from marc_pd_tool.core.domain.enums import CountryClassification
from marc_pd_tool.core.domain.match_result import MatchResult
from marc_pd_tool.core.domain.publication import Publication


class TestCopyrightStatusSanityChecks:
    """Basic sanity checks for copyright status determination

    Comprehensive testing is handled by Hypothesis in test_copyright_status_hypothesis.py
    """

    def test_us_pre_1929_is_public_domain(self):
        """Verify pre-1929 US works are public domain"""
        pub = Publication(
            title="Old Book",
            author="Old Author",
            pub_date="1920",
            country_classification=CountryClassification.US,
        )

        status = pub.determine_copyright_status()
        current_year = datetime.now().year
        expected_year = current_year - 96
        assert status == f"US_PRE_{expected_year}"
        assert pub.status_rule == CopyrightStatusRule.US_PRE_COPYRIGHT_EXPIRATION

    def test_us_1955_registered_not_renewed(self):
        """Verify 1955 US work with registration but no renewal"""
        pub = Publication(
            title="Mid-Century Book",
            author="Test Author",
            pub_date="1955",
            country_classification=CountryClassification.US,
        )

        # Add registration but no renewal
        pub.registration_match = MatchResult(
            matched_title="Mid-Century Book",
            matched_author="Test Author",
            similarity_score=95.0,
            title_score=98.0,
            author_score=92.0,
            year_difference=0,
            source_id="reg_12345",
            source_type="registration",
        )

        status = pub.determine_copyright_status()
        assert status == CopyrightStatus.US_REGISTERED_NOT_RENEWED.value
        assert pub.status_rule == CopyrightStatusRule.US_RENEWAL_PERIOD_NOT_RENEWED

    def test_us_1955_renewed_is_copyrighted(self):
        """Verify 1955 US work with renewal is still copyrighted"""
        pub = Publication(
            title="Renewed Book",
            author="Test Author",
            pub_date="1955",
            country_classification=CountryClassification.US,
        )

        # Add both registration and renewal
        pub.registration_match = MatchResult(
            matched_title="Renewed Book",
            matched_author="Test Author",
            similarity_score=95.0,
            title_score=98.0,
            author_score=92.0,
            year_difference=0,
            source_id="reg_12345",
            source_type="registration",
        )

        pub.renewal_match = MatchResult(
            matched_title="Renewed Book",
            matched_author="Test Author",
            similarity_score=93.0,
            title_score=96.0,
            author_score=90.0,
            year_difference=0,
            source_id="ren_67890",
            source_type="renewal",
        )

        status = pub.determine_copyright_status()
        assert status == CopyrightStatus.US_RENEWED.value
        assert pub.status_rule == CopyrightStatusRule.US_RENEWAL_PERIOD_RENEWED

    def test_foreign_work_includes_country_code(self):
        """Verify foreign works append country code to status"""
        pub = Publication(
            title="British Book",
            author="British Author",
            pub_date="1960",
            country_classification=CountryClassification.NON_US,
            country_code="GBR",
        )

        # No matches
        status = pub.determine_copyright_status()
        assert status == f"{CopyrightStatus.FOREIGN_NO_MATCH.value}_GBR"
        assert pub.status_rule == CopyrightStatusRule.FOREIGN_NO_MATCH

    def test_unknown_country_has_special_status(self):
        """Verify unknown country has its own status codes"""
        pub = Publication(
            title="Mystery Book",
            author="Unknown Author",
            pub_date="1970",
            country_classification=CountryClassification.UNKNOWN,
        )

        # No matches
        status = pub.determine_copyright_status()
        assert status == CopyrightStatus.COUNTRY_UNKNOWN_NO_MATCH.value
        assert pub.status_rule == CopyrightStatusRule.COUNTRY_UNKNOWN_NO_MATCH

    def test_no_year_uses_general_logic(self):
        """Verify publications without year still get processed"""
        pub = Publication(
            title="Dateless Book",
            author="Test Author",
            pub_date="",  # No date
            country_classification=CountryClassification.US,
        )

        # Add registration
        pub.registration_match = MatchResult(
            matched_title="Dateless Book",
            matched_author="Test Author",
            similarity_score=90.0,
            title_score=95.0,
            author_score=85.0,
            year_difference=0,
            source_id="reg_99999",
            source_type="registration",
        )

        status = pub.determine_copyright_status()
        assert status == CopyrightStatus.US_REGISTERED_NOT_RENEWED.value
        assert pub.status_rule == CopyrightStatusRule.US_REGISTERED_NO_RENEWAL

    def test_beyond_data_range_gets_special_status(self):
        """Verify works beyond 1991 get OUT_OF_DATA_RANGE status"""
        pub = Publication(
            title="Modern Book",
            author="Modern Author",
            pub_date="1995",
            country_classification=CountryClassification.US,
        )

        status = pub.determine_copyright_status()
        assert status == "OUT_OF_DATA_RANGE_1991"
        assert pub.status_rule == CopyrightStatusRule.OUT_OF_DATA_RANGE
