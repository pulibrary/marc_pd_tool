"""Enums for copyright status and country classification"""

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
