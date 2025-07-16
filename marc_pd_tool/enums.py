"""Enums for copyright status and country classification"""

from enum import Enum


class CountryClassification(Enum):
    """Country classification for copyright analysis"""
    US = "US"
    NON_US = "Non-US"
    UNKNOWN = "Unknown"


class CopyrightStatus(Enum):
    """Final copyright status classification based on registration/renewal patterns"""
    POTENTIALLY_PD_DATE_VERIFY = "Potentially PD (date verify)"
    POTENTIALLY_IN_COPYRIGHT = "Potentially In-Copyright" 
    RESEARCH_US_STATUS = "Research for US status"
    RESEARCH_US_ONLY_PD = "Research for potential US-only PD status"
    UNKNOWN = "Unknown"