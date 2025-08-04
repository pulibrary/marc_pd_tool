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
    PD_PRE_1928 = "PD_PRE_1928"  # Published before 1928
    PD_US_1930_1963_NOT_RENEWED = (
        "PD_US_1930_1963_NOT_RENEWED"  # US 1930-1963 with registration but no renewal
    )

    # Likely public domain but needs verification
    PD_US_NO_REG_DATA = "PD_US_NO_REG_DATA"  # US work with no registration data found
    PD_US_REG_NO_RENEWAL = (
        "PD_US_REG_NO_RENEWAL"  # US work registered but no renewal found (outside 1930-1963)
    )

    # Unknown/needs research
    UNKNOWN_US_1930_1963_NO_DATA = (
        "UNKNOWN_US_1930_1963_NO_DATA"  # US 1930-1963 with no reg/renewal data
    )

    # In copyright
    IN_COPYRIGHT = "IN_COPYRIGHT"  # Has renewal or other evidence of copyright
    IN_COPYRIGHT_US_1930_1963_RENEWED = (
        "IN_COPYRIGHT_US_1930_1963_RENEWED"  # US 1930-1963 that was renewed
    )

    # Non-US works
    RESEARCH_US_STATUS = "RESEARCH_US_STATUS"  # Non-US with US activity
    RESEARCH_US_ONLY_PD = "RESEARCH_US_ONLY_PD"  # Non-US with no US activity

    # Unknown country
    COUNTRY_UNKNOWN = "COUNTRY_UNKNOWN"  # Country of publication unknown

    # Legacy status for backward compatibility (deprecated)
    PD_DATE_VERIFY = "PD_DATE_VERIFY"  # Deprecated - use specific statuses above
    PD_NO_RENEWAL = "PD_NO_RENEWAL"  # Deprecated - use PD_US_1930_1963_NOT_RENEWED


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

    # US Pre-1928 - Always public domain
    US_PRE_1928 = "us_pre_1928"  # Published before 1928 in US

    # US 1930-1963 Special Rules
    US_1930_1963_NO_RENEWAL = "us_1930_1963_no_renewal"  # Registered but not renewed (PD)
    US_1930_1963_RENEWED = "us_1930_1963_renewed"  # Registered and renewed (in copyright)
    US_1930_1963_NO_REG_DATA = "us_1930_1963_no_reg_data"  # No registration data found (unknown)

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
    CopyrightStatusRule.US_PRE_1928: "Published before 1928 (public domain)",
    CopyrightStatusRule.US_1930_1963_NO_RENEWAL: (
        "US 1930-1963: Registered but not renewed (public domain)"
    ),
    CopyrightStatusRule.US_1930_1963_RENEWED: "US 1930-1963: Registered and renewed (in copyright)",
    CopyrightStatusRule.US_1930_1963_NO_REG_DATA: (
        "US 1930-1963: No registration data found (unknown)"
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
