# marc_pd_tool/data/enums.py

"""Enumerations used across the MARC PD tool"""

# Standard library imports
from enum import Enum


class CountryClassification(Enum):
    """Country classification for copyright analysis"""

    US = "US"
    NON_US = "Non-US"
    UNKNOWN = "Unknown"


class CopyrightStatus(Enum):
    """Final copyright status classification based on registration/renewal patterns"""

    # Definitely public domain
    PD_PRE_MIN_YEAR = "PD_PRE_MIN_YEAR"  # Published before min_year (current_year - 96)
    PD_US_NOT_RENEWED = (
        "PD_US_NOT_RENEWED"  # US works with registration but no renewal (min_year-1977)
    )

    # Likely public domain but needs verification
    PD_US_NO_REG_DATA = "PD_US_NO_REG_DATA"  # US work with no registration data found
    PD_US_REG_NO_RENEWAL = (
        "PD_US_REG_NO_RENEWAL"  # US work registered but no renewal found (outside 1930-1963)
    )

    # Unknown/needs research
    UNKNOWN_US_NO_DATA = "UNKNOWN_US_NO_DATA"  # US works in renewal period with no reg/renewal data

    # In copyright
    IN_COPYRIGHT = "IN_COPYRIGHT"  # Has renewal or other evidence of copyright
    IN_COPYRIGHT_US_RENEWED = (
        "IN_COPYRIGHT_US_RENEWED"  # US works in renewal period that were renewed
    )

    # Non-US works
    RESEARCH_US_STATUS = "RESEARCH_US_STATUS"  # Non-US with US activity
    RESEARCH_US_ONLY_PD = "RESEARCH_US_ONLY_PD"  # Non-US with no US activity

    # Unknown country
    COUNTRY_UNKNOWN = "COUNTRY_UNKNOWN"  # Country of publication unknown


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

    # US Pre-min_year - Always public domain
    US_PRE_MIN_YEAR = "us_pre_min_year"  # Published before min_year (current_year - 96)

    # US renewal period rules (min_year through 1977)
    US_NOT_RENEWED = "us_not_renewed"  # Registered but not renewed (PD)
    US_RENEWED = "us_renewed"  # Registered and renewed (in copyright)
    US_NO_REG_DATA_RENEWAL_PERIOD = (
        "us_no_reg_data_renewal_period"  # No registration data found (unknown)
    )

    # General US Rules
    US_REGISTERED_NO_RENEWAL = "us_registered_no_renewal"  # Registered but no renewal found
    US_RENEWAL_FOUND = "us_renewal_found"  # Renewal found (likely in copyright)
    US_NO_REG_DATA = "us_no_reg_data"  # No registration or renewal data
    US_REGISTERED_AND_RENEWED = "us_registered_and_renewed"  # Both registration and renewal

    # Foreign Works
    FOREIGN_US_ACTIVITY = "foreign_us_activity"  # Non-US work with US copyright activity
    FOREIGN_NO_US_ACTIVITY = "foreign_no_us_activity"  # Non-US work with no US activity

    # Unknown/Other
    UNKNOWN_COUNTRY = "unknown_country"  # Country of publication unknown
    MISSING_YEAR = "missing_year"  # No publication year available


# Human-readable descriptions for status rules
STATUS_RULE_DESCRIPTIONS = {
    CopyrightStatusRule.US_PRE_MIN_YEAR: "Published before current year - 96 (public domain)",
    CopyrightStatusRule.US_NOT_RENEWED: (
        "US renewal period: Registered but not renewed (public domain)"
    ),
    CopyrightStatusRule.US_RENEWED: "US renewal period: Registered and renewed (in copyright)",
    CopyrightStatusRule.US_NO_REG_DATA_RENEWAL_PERIOD: (
        "US renewal period: No registration data found (unknown)"
    ),
    CopyrightStatusRule.US_REGISTERED_NO_RENEWAL: "US: Registered but no renewal found",
    CopyrightStatusRule.US_RENEWAL_FOUND: "US: Renewal record found (likely in copyright)",
    CopyrightStatusRule.US_NO_REG_DATA: "US: No registration or renewal data found",
    CopyrightStatusRule.US_REGISTERED_AND_RENEWED: (
        "US: Both registration and renewal found (in copyright)"
    ),
    CopyrightStatusRule.FOREIGN_US_ACTIVITY: "Non-US work with US copyright activity",
    CopyrightStatusRule.FOREIGN_NO_US_ACTIVITY: "Non-US work with no US copyright records",
    CopyrightStatusRule.UNKNOWN_COUNTRY: "Country of publication unknown",
    CopyrightStatusRule.MISSING_YEAR: "No publication year available",
}
