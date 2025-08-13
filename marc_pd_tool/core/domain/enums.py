# marc_pd_tool/core/domain/enums.py

"""Domain enumerations for the MARC PD tool"""

# Standard library imports
from enum import Enum


class CountryClassification(Enum):
    """Country classification for copyright analysis"""

    US = "US"
    NON_US = "Non-US"
    UNKNOWN = "Unknown"


class CopyrightStatus(Enum):
    """Final copyright status classification based on registration/renewal patterns

    Note: Some statuses are dynamically generated and not listed here:
    - US_PRE_{YEAR} (e.g., US_PRE_1929)
    - FOREIGN_PRE_{YEAR}_{COUNTRY} (e.g., FOREIGN_PRE_1929_GBR)
    - OUT_OF_DATA_RANGE_{YEAR} (e.g., OUT_OF_DATA_RANGE_1991)
    - FOREIGN_RENEWED_{COUNTRY}
    - FOREIGN_REGISTERED_NOT_RENEWED_{COUNTRY}
    - FOREIGN_NO_MATCH_{COUNTRY}
    """

    # US works with clear match results
    US_RENEWED = "US_RENEWED"  # US works found to be renewed
    US_REGISTERED_NOT_RENEWED = "US_REGISTERED_NOT_RENEWED"  # US works registered but not renewed
    US_NO_MATCH = "US_NO_MATCH"  # US works with no registration or renewal found

    # Foreign works (country code appended dynamically)
    FOREIGN_RENEWED = "FOREIGN_RENEWED"  # Base for foreign renewed works
    FOREIGN_REGISTERED_NOT_RENEWED = "FOREIGN_REGISTERED_NOT_RENEWED"  # Base for foreign registered
    FOREIGN_NO_MATCH = "FOREIGN_NO_MATCH"  # Base for foreign no match

    # Unknown country works
    COUNTRY_UNKNOWN_RENEWED = "COUNTRY_UNKNOWN_RENEWED"  # Unknown country, found renewal
    COUNTRY_UNKNOWN_REGISTERED_NOT_RENEWED = (
        "COUNTRY_UNKNOWN_REGISTERED_NOT_RENEWED"  # Unknown country, reg only
    )
    COUNTRY_UNKNOWN_NO_MATCH = "COUNTRY_UNKNOWN_NO_MATCH"  # Unknown country, no matches

    # Special statuses (generated dynamically in practice)
    PRE_COPYRIGHT_EXPIRATION = (
        "PRE_COPYRIGHT_EXPIRATION"  # Placeholder for dynamic pre-expiration statuses
    )
    OUT_OF_DATA_RANGE = "OUT_OF_DATA_RANGE"  # Placeholder for dynamic out-of-range statuses


class MatchType(Enum):
    """Type of match found between MARC record and copyright/renewal data"""

    LCCN = "lccn"  # Match based on Library of Congress Control Number
    SIMILARITY = "similarity"  # Match based on title/author similarity scores
    BRUTE_FORCE_WITHOUT_YEAR = "brute_force_without_year"  # Match for records without year data


class CopyrightStatusRule(Enum):
    """Legal reasoning for copyright status determination

    These rules explain WHY a particular copyright status was assigned,
    based on the combination of country, year, and registration/renewal data.
    """

    # Pre-copyright expiration (dynamically determined)
    US_PRE_COPYRIGHT_EXPIRATION = (
        "us_pre_copyright_expiration"  # Published before current_year - 96
    )
    FOREIGN_PRE_COPYRIGHT_EXPIRATION = (
        "foreign_pre_copyright_expiration"  # Foreign work before expiration
    )

    # US renewal period rules (copyright_expiration_year through 1977)
    US_RENEWAL_PERIOD_NOT_RENEWED = "us_renewal_period_not_renewed"  # Registered but not renewed
    US_RENEWAL_PERIOD_RENEWED = "us_renewal_period_renewed"  # Registered and renewed
    US_RENEWAL_PERIOD_NO_MATCH = "us_renewal_period_no_match"  # No registration found

    # US works outside renewal period
    US_REGISTERED_NO_RENEWAL = "us_registered_no_renewal"  # Registered but no renewal found
    US_RENEWAL_FOUND = "us_renewal_found"  # Renewal record found
    US_NO_MATCH = "us_no_match"  # No registration or renewal data
    US_BOTH_REG_AND_RENEWAL = "us_both_reg_and_renewal"  # Both registration and renewal

    # Foreign Works
    FOREIGN_RENEWED = "foreign_renewed"  # Foreign work with renewal
    FOREIGN_REGISTERED_NOT_RENEWED = (
        "foreign_registered_not_renewed"  # Foreign work registered only
    )
    FOREIGN_NO_MATCH = "foreign_no_match"  # Foreign work with no US activity

    # Unknown country
    COUNTRY_UNKNOWN_RENEWED = "country_unknown_renewed"  # Unknown country with renewal
    COUNTRY_UNKNOWN_REGISTERED = "country_unknown_registered"  # Unknown country registered only
    COUNTRY_UNKNOWN_NO_MATCH = "country_unknown_no_match"  # Unknown country no matches

    # Data limitations
    OUT_OF_DATA_RANGE = "out_of_data_range"  # Year beyond our data coverage
    MISSING_YEAR = "missing_year"  # No publication year available


# Human-readable descriptions for status rules
STATUS_RULE_DESCRIPTIONS = {
    CopyrightStatusRule.US_PRE_COPYRIGHT_EXPIRATION: "Published before copyright expiration year",
    CopyrightStatusRule.FOREIGN_PRE_COPYRIGHT_EXPIRATION: (
        "Foreign work published before copyright expiration"
    ),
    CopyrightStatusRule.US_RENEWAL_PERIOD_NOT_RENEWED: (
        "US renewal period: Registered but not renewed"
    ),
    CopyrightStatusRule.US_RENEWAL_PERIOD_RENEWED: "US renewal period: Registered and renewed",
    CopyrightStatusRule.US_RENEWAL_PERIOD_NO_MATCH: "US renewal period: No registration data found",
    CopyrightStatusRule.US_REGISTERED_NO_RENEWAL: "US: Registered but no renewal found",
    CopyrightStatusRule.US_RENEWAL_FOUND: "US: Renewal record found",
    CopyrightStatusRule.US_NO_MATCH: "US: No registration or renewal data found",
    CopyrightStatusRule.US_BOTH_REG_AND_RENEWAL: "US: Both registration and renewal found",
    CopyrightStatusRule.FOREIGN_RENEWED: "Foreign work with US renewal",
    CopyrightStatusRule.FOREIGN_REGISTERED_NOT_RENEWED: "Foreign work with US registration only",
    CopyrightStatusRule.FOREIGN_NO_MATCH: "Foreign work with no US copyright records",
    CopyrightStatusRule.COUNTRY_UNKNOWN_RENEWED: "Unknown country with renewal found",
    CopyrightStatusRule.COUNTRY_UNKNOWN_REGISTERED: "Unknown country with registration only",
    CopyrightStatusRule.COUNTRY_UNKNOWN_NO_MATCH: "Unknown country with no matches",
    CopyrightStatusRule.OUT_OF_DATA_RANGE: "Year beyond available copyright data",
    CopyrightStatusRule.MISSING_YEAR: "No publication year available",
}
