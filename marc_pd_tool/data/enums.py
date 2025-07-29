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

    PD_DATE_VERIFY = "PD_DATE_VERIFY"
    PD_NO_RENEWAL = "PD_NO_RENEWAL"
    IN_COPYRIGHT = "IN_COPYRIGHT"
    RESEARCH_US_STATUS = "RESEARCH_US_STATUS"
    RESEARCH_US_ONLY_PD = "RESEARCH_US_ONLY_PD"
    COUNTRY_UNKNOWN = "COUNTRY_UNKNOWN"


class MatchType(Enum):
    """Type of match found between MARC record and copyright/renewal data"""

    LCCN = "lccn"  # Match based on Library of Congress Control Number
    SIMILARITY = "similarity"  # Match based on title/author similarity scores
    BRUTE_FORCE_WITHOUT_YEAR = "brute_force_without_year"  # Match for records without year data
