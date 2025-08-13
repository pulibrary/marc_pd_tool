# tests/test_data/test_copyright_status_hypothesis.py

"""Hypothesis-based property tests for copyright status determination"""

# Standard library imports
from datetime import datetime

# Third party imports
from hypothesis import given
from hypothesis import strategies as st

# Local imports
from marc_pd_tool.core.domain.enums import CopyrightStatus
from marc_pd_tool.core.domain.enums import CopyrightStatusRule
from marc_pd_tool.core.domain.enums import CountryClassification
from marc_pd_tool.core.domain.match_result import MatchResult
from marc_pd_tool.core.domain.publication import Publication

# Define year ranges for testing
CURRENT_YEAR = datetime.now().year
COPYRIGHT_EXPIRATION_YEAR = CURRENT_YEAR - 96  # 1929 for 2025
MAX_DATA_YEAR = 1991  # Maximum year of available copyright/renewal data

# Year range strategies
pre_copyright_expiration = st.integers(min_value=1800, max_value=COPYRIGHT_EXPIRATION_YEAR - 1)
renewal_period = st.integers(min_value=COPYRIGHT_EXPIRATION_YEAR, max_value=1977)
special_rule_period = st.integers(min_value=1930, max_value=1963)  # Special US rule
post_renewal_period = st.integers(min_value=1978, max_value=MAX_DATA_YEAR)
beyond_data_range = st.integers(min_value=MAX_DATA_YEAR + 1, max_value=2099)
any_valid_year = st.integers(min_value=1800, max_value=2099)
year_or_none = st.one_of(st.none(), any_valid_year)

# Country classification strategy
country_classification = st.sampled_from(CountryClassification)

# Country code strategy (for foreign publications)
country_code = st.one_of(
    st.none(), st.sampled_from(["GBR", "FRA", "DEU", "ITA", "ESP", "JPN", "CHN"])
)


# Match result builder
@st.composite
def match_result(draw, source_type="registration"):
    """Generate a valid MatchResult"""
    return MatchResult(
        matched_title=draw(st.text(min_size=1, max_size=50)),
        matched_author=draw(st.text(min_size=1, max_size=50)),
        similarity_score=draw(st.floats(min_value=0.0, max_value=100.0)),
        title_score=draw(st.floats(min_value=0.0, max_value=100.0)),
        author_score=draw(st.floats(min_value=0.0, max_value=100.0)),
        year_difference=draw(st.integers(min_value=0, max_value=5)),
        source_id=f"{source_type}_{draw(st.integers(min_value=1, max_value=10000))}",
        source_type=source_type,
    )


class TestUSCopyrightStatusProperties:
    """Property-based tests for US copyright status determination"""

    @given(year=pre_copyright_expiration)
    def test_us_pre_copyright_expiration_always_public_domain(self, year):
        """Any US work before copyright expiration year is public domain"""
        pub = Publication(
            title="Test Book",
            author="Test Author",
            pub_date=str(year),
            country_classification=CountryClassification.US,
        )

        # Add any combination of matches - shouldn't matter
        pub.registration_match = MatchResult(
            matched_title="Test",
            matched_author="Test",
            similarity_score=90,
            title_score=90,
            author_score=90,
            year_difference=0,
            source_id="reg_1",
            source_type="registration",
        )

        status = pub.determine_copyright_status()
        assert status.startswith("US_PRE_")
        assert pub.status_rule == CopyrightStatusRule.US_PRE_COPYRIGHT_EXPIRATION

    @given(year=special_rule_period, has_reg=st.booleans(), has_ren=st.booleans())
    def test_us_special_rule_1930_1963(self, year, has_reg, has_ren):
        """Test special rule for US works 1930-1963"""
        pub = Publication(
            title="Test Book",
            author="Test Author",
            pub_date=str(year),
            country_classification=CountryClassification.US,
        )

        if has_reg:
            pub.registration_match = MatchResult(
                matched_title="Test",
                matched_author="Test",
                similarity_score=90,
                title_score=90,
                author_score=90,
                year_difference=0,
                source_id="reg_1",
                source_type="registration",
            )

        if has_ren:
            pub.renewal_match = MatchResult(
                matched_title="Test",
                matched_author="Test",
                similarity_score=90,
                title_score=90,
                author_score=90,
                year_difference=0,
                source_id="ren_1",
                source_type="renewal",
            )

        status = pub.determine_copyright_status()

        # Expected outcomes for 1930-1963
        if has_ren:
            assert status == CopyrightStatus.US_RENEWED.value
        elif has_reg:
            assert status == CopyrightStatus.US_REGISTERED_NOT_RENEWED.value
        else:
            assert status == CopyrightStatus.US_NO_MATCH.value

    @given(year=renewal_period, has_reg=st.booleans(), has_ren=st.booleans())
    def test_us_renewal_period_status(self, year, has_reg, has_ren):
        """Test US works in renewal period (1929-1977)"""
        pub = Publication(
            title="Test Book",
            author="Test Author",
            pub_date=str(year),
            country_classification=CountryClassification.US,
        )

        if has_reg:
            pub.registration_match = MatchResult(
                matched_title="Test",
                matched_author="Test",
                similarity_score=90,
                title_score=90,
                author_score=90,
                year_difference=0,
                source_id="reg_1",
                source_type="registration",
            )

        if has_ren:
            pub.renewal_match = MatchResult(
                matched_title="Test",
                matched_author="Test",
                similarity_score=90,
                title_score=90,
                author_score=90,
                year_difference=0,
                source_id="ren_1",
                source_type="renewal",
            )

        status = pub.determine_copyright_status()

        # In renewal period: renewal determines copyright
        if has_ren:
            assert status == CopyrightStatus.US_RENEWED.value
            assert pub.status_rule == CopyrightStatusRule.US_RENEWAL_PERIOD_RENEWED
        elif has_reg:
            assert status == CopyrightStatus.US_REGISTERED_NOT_RENEWED.value
            assert pub.status_rule == CopyrightStatusRule.US_RENEWAL_PERIOD_NOT_RENEWED
        else:
            assert status == CopyrightStatus.US_NO_MATCH.value
            assert pub.status_rule == CopyrightStatusRule.US_RENEWAL_PERIOD_NO_MATCH

    @given(year=post_renewal_period, has_reg=st.booleans(), has_ren=st.booleans())
    def test_us_post_renewal_period_status(self, year, has_reg, has_ren):
        """Test US works after renewal period (1978-1991)"""
        pub = Publication(
            title="Test Book",
            author="Test Author",
            pub_date=str(year),
            country_classification=CountryClassification.US,
        )

        if has_reg:
            pub.registration_match = MatchResult(
                matched_title="Test",
                matched_author="Test",
                similarity_score=90,
                title_score=90,
                author_score=90,
                year_difference=0,
                source_id="reg_1",
                source_type="registration",
            )

        if has_ren:
            pub.renewal_match = MatchResult(
                matched_title="Test",
                matched_author="Test",
                similarity_score=90,
                title_score=90,
                author_score=90,
                year_difference=0,
                source_id="ren_1",
                source_type="renewal",
            )

        status = pub.determine_copyright_status()

        # After 1977: different logic applies
        if has_ren:
            assert status == CopyrightStatus.US_RENEWED.value
        elif has_reg:
            assert status == CopyrightStatus.US_REGISTERED_NOT_RENEWED.value
        else:
            assert status == CopyrightStatus.US_NO_MATCH.value

    @given(year=beyond_data_range)
    def test_us_beyond_data_range(self, year):
        """Test US works beyond our data range (post-1991)"""
        pub = Publication(
            title="Test Book",
            author="Test Author",
            pub_date=str(year),
            country_classification=CountryClassification.US,
        )

        status = pub.determine_copyright_status()
        assert status == f"OUT_OF_DATA_RANGE_{MAX_DATA_YEAR}"
        assert pub.status_rule == CopyrightStatusRule.OUT_OF_DATA_RANGE

    @given(has_reg=st.booleans(), has_ren=st.booleans())
    def test_us_no_year_uses_general_logic(self, has_reg, has_ren):
        """Test US works without year information"""
        pub = Publication(
            title="Test Book",
            author="Test Author",
            pub_date="",  # No year
            country_classification=CountryClassification.US,
        )

        if has_reg:
            pub.registration_match = MatchResult(
                matched_title="Test",
                matched_author="Test",
                similarity_score=90,
                title_score=90,
                author_score=90,
                year_difference=0,
                source_id="reg_1",
                source_type="registration",
            )

        if has_ren:
            pub.renewal_match = MatchResult(
                matched_title="Test",
                matched_author="Test",
                similarity_score=90,
                title_score=90,
                author_score=90,
                year_difference=0,
                source_id="ren_1",
                source_type="renewal",
            )

        status = pub.determine_copyright_status()

        # Without year, use general US logic
        if has_ren:
            assert status == CopyrightStatus.US_RENEWED.value
        elif has_reg:
            assert status == CopyrightStatus.US_REGISTERED_NOT_RENEWED.value
        else:
            assert status == CopyrightStatus.US_NO_MATCH.value


class TestForeignCopyrightStatusProperties:
    """Property-based tests for foreign copyright status determination"""

    @given(year=year_or_none, has_reg=st.booleans(), has_ren=st.booleans(), code=country_code)
    def test_foreign_status_with_country_code(self, year, has_reg, has_ren, code):
        """Test foreign works append country code to status"""
        pub = Publication(
            title="Test Book",
            author="Test Author",
            pub_date=str(year) if year else "",
            country_classification=CountryClassification.NON_US,
            country_code=code,
        )

        if has_reg:
            pub.registration_match = MatchResult(
                matched_title="Test",
                matched_author="Test",
                similarity_score=90,
                title_score=90,
                author_score=90,
                year_difference=0,
                source_id="reg_1",
                source_type="registration",
            )

        if has_ren:
            pub.renewal_match = MatchResult(
                matched_title="Test",
                matched_author="Test",
                similarity_score=90,
                title_score=90,
                author_score=90,
                year_difference=0,
                source_id="ren_1",
                source_type="renewal",
            )

        status = pub.determine_copyright_status()

        # Check for pre-expiration first
        if year and year < COPYRIGHT_EXPIRATION_YEAR:
            assert f"FOREIGN_PRE_{COPYRIGHT_EXPIRATION_YEAR}" in status
        elif year and year > MAX_DATA_YEAR:
            assert status == f"OUT_OF_DATA_RANGE_{MAX_DATA_YEAR}"
        else:
            # Foreign works prioritize renewal over registration
            if has_ren:
                assert status.startswith(CopyrightStatus.FOREIGN_RENEWED.value)
            elif has_reg:
                assert status.startswith(CopyrightStatus.FOREIGN_REGISTERED_NOT_RENEWED.value)
            else:
                assert status.startswith(CopyrightStatus.FOREIGN_NO_MATCH.value)

            # Country code should be appended if present (unless out of range)
            if code and not (year and year > MAX_DATA_YEAR):
                assert status.endswith(f"_{code}")


class TestUnknownCountryStatusProperties:
    """Property-based tests for unknown country status determination"""

    @given(year=year_or_none, has_reg=st.booleans(), has_ren=st.booleans())
    def test_unknown_country_status(self, year, has_reg, has_ren):
        """Test publications with unknown country"""
        pub = Publication(
            title="Test Book",
            author="Test Author",
            pub_date=str(year) if year else "",
            country_classification=CountryClassification.UNKNOWN,
        )

        if has_reg:
            pub.registration_match = MatchResult(
                matched_title="Test",
                matched_author="Test",
                similarity_score=90,
                title_score=90,
                author_score=90,
                year_difference=0,
                source_id="reg_1",
                source_type="registration",
            )

        if has_ren:
            pub.renewal_match = MatchResult(
                matched_title="Test",
                matched_author="Test",
                similarity_score=90,
                title_score=90,
                author_score=90,
                year_difference=0,
                source_id="ren_1",
                source_type="renewal",
            )

        status = pub.determine_copyright_status()

        # Check for pre-expiration first
        if year and year < COPYRIGHT_EXPIRATION_YEAR:
            assert f"COUNTRY_UNKNOWN_PRE_{COPYRIGHT_EXPIRATION_YEAR}" in status
        elif year and year > MAX_DATA_YEAR:
            assert status == f"OUT_OF_DATA_RANGE_{MAX_DATA_YEAR}"
        else:
            if has_ren:
                assert status == CopyrightStatus.COUNTRY_UNKNOWN_RENEWED.value
            elif has_reg:
                assert status == CopyrightStatus.COUNTRY_UNKNOWN_REGISTERED_NOT_RENEWED.value
            else:
                assert status == CopyrightStatus.COUNTRY_UNKNOWN_NO_MATCH.value


class TestCopyrightStatusConsistency:
    """Test consistency and edge cases"""

    @given(
        year=year_or_none,
        country=country_classification,
        has_reg=st.booleans(),
        has_ren=st.booleans(),
    )
    def test_status_determination_is_deterministic(self, year, country, has_reg, has_ren):
        """Same inputs should always produce same status"""
        pub = Publication(
            title="Test Book",
            author="Test Author",
            pub_date=str(year) if year else "",
            country_classification=country,
        )

        if has_reg:
            pub.registration_match = MatchResult(
                matched_title="Test",
                matched_author="Test",
                similarity_score=90,
                title_score=90,
                author_score=90,
                year_difference=0,
                source_id="reg_1",
                source_type="registration",
            )

        if has_ren:
            pub.renewal_match = MatchResult(
                matched_title="Test",
                matched_author="Test",
                similarity_score=90,
                title_score=90,
                author_score=90,
                year_difference=0,
                source_id="ren_1",
                source_type="renewal",
            )

        # Call multiple times
        status1 = pub.determine_copyright_status()
        status2 = pub.determine_copyright_status()
        status3 = pub.determine_copyright_status()

        # All should be identical
        assert status1 == status2 == status3
        assert pub.copyright_status == status1

    @given(
        year=any_valid_year,
        country=country_classification,
        has_reg=st.booleans(),
        has_ren=st.booleans(),
    )
    def test_status_is_always_set(self, year, country, has_reg, has_ren):
        """Every combination should produce a valid status"""
        pub = Publication(
            title="Test Book",
            author="Test Author",
            pub_date=str(year),
            country_classification=country,
        )

        if has_reg:
            pub.registration_match = MatchResult(
                matched_title="Test",
                matched_author="Test",
                similarity_score=90,
                title_score=90,
                author_score=90,
                year_difference=0,
                source_id="reg_1",
                source_type="registration",
            )

        if has_ren:
            pub.renewal_match = MatchResult(
                matched_title="Test",
                matched_author="Test",
                similarity_score=90,
                title_score=90,
                author_score=90,
                year_difference=0,
                source_id="ren_1",
                source_type="renewal",
            )

        status = pub.determine_copyright_status()

        # Status should always be set
        assert status is not None
        assert isinstance(status, str)
        assert len(status) > 0
        assert pub.copyright_status == status

        # Status rule should also be set
        assert pub.status_rule is not None
        assert isinstance(pub.status_rule, CopyrightStatusRule)

    def test_boundary_years(self):
        """Test critical boundary years"""
        critical_years = [
            COPYRIGHT_EXPIRATION_YEAR - 1,  # Last year before expiration
            COPYRIGHT_EXPIRATION_YEAR,  # First year of renewal period
            1929,  # Common boundary
            1930,  # Start of special rule
            1963,  # End of special rule
            1964,  # Just after special rule
            1977,  # End of renewal period
            1978,  # Start of post-renewal
            1991,  # Last year of data
            1992,  # First year beyond data
        ]

        for year in critical_years:
            pub = Publication(
                title=f"Book {year}",
                author="Author",
                pub_date=str(year),
                country_classification=CountryClassification.US,
            )

            # Should not crash
            status = pub.determine_copyright_status()
            assert status is not None

            # Verify year-based rules
            if year < COPYRIGHT_EXPIRATION_YEAR:
                assert "US_PRE_" in status
            elif year > 1991:
                assert "OUT_OF_DATA_RANGE" in status
            else:
                # Should be one of the valid US statuses
                assert "US_" in status or "OUT_OF_DATA_RANGE" in status
