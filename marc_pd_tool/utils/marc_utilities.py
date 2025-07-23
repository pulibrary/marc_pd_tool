# marc_pd_tool/utils/marc_utilities.py

"""MARC data processing utilities and constants"""

# Standard library imports

# Local imports
from marc_pd_tool.data.enums import CountryClassification

# Official MARC country codes for US (from Library of Congress)
US_COUNTRY_CODES = {
    "aku",
    "alu",
    "aru",
    "azu",
    "cau",
    "cou",
    "ctu",
    "dcu",
    "deu",
    "flu",
    "gau",
    "hiu",
    "iau",
    "idu",
    "ilu",
    "inu",
    "ksu",
    "kyu",
    "lau",
    "mau",
    "mdu",
    "meu",
    "miu",
    "mnu",
    "mou",
    "msu",
    "mtu",
    "nbu",
    "ncu",
    "ndu",
    "nhu",
    "nju",
    "nmu",
    "nvu",
    "nyu",
    "ohu",
    "oku",
    "oru",
    "pau",
    "riu",
    "scu",
    "sdu",
    "tnu",
    "txu",
    "utu",
    "vau",
    "vtu",
    "wau",
    "wvu",
    "wyu",
    "xxu",
}


def extract_country_from_marc_008(field_008: str) -> tuple[str, CountryClassification]:
    """Extract country code from MARC 008 field and classify as US/Non-US

    Args:
        field_008: MARC 008 control field string

    Returns:
        Tuple of (country_code, classification)
    """
    if len(field_008) < 18:
        return "", CountryClassification.UNKNOWN

    # Country code is at positions 15-17 (0-indexed)
    country_code = field_008[15:18].strip()

    if not country_code:
        return "", CountryClassification.UNKNOWN

    # Check against official US codes
    classification = (
        CountryClassification.US
        if country_code.lower() in US_COUNTRY_CODES
        else CountryClassification.NON_US
    )

    return country_code, classification


# Official MARC language codes mapping to our processing languages
MARC_LANGUAGE_MAPPING = {
    # English variants
    "eng": "eng",
    "en": "eng",
    # French variants
    "fre": "fre",
    "fr": "fre",
    "fra": "fre",
    # German variants
    "ger": "ger",
    "de": "ger",
    "deu": "ger",
    # Spanish variants
    "spa": "spa",
    "es": "spa",
    "esp": "spa",
    # Italian variants
    "ita": "ita",
    "it": "ita",
    "ital": "ita",
}


def extract_language_from_marc(marc_language_code: str) -> tuple[str, str]:
    """Extract and map MARC language code to processing language

    Args:
        marc_language_code: Language code from MARC record (008 or 041 field)

    Returns:
        Tuple of (processing_language, detection_status)
        - processing_language: One of eng, fre, ger, spa, ita, or 'eng' for fallback
        - detection_status: 'detected', 'fallback_english', or 'unknown_code'
    """
    if not marc_language_code:
        return "eng", "fallback_english"

    # Clean and normalize the language code
    clean_code = marc_language_code.strip().lower()

    # If code is empty after stripping, treat as fallback
    if not clean_code:
        return "eng", "fallback_english"

    # Check if we have a mapping for this code
    if clean_code in MARC_LANGUAGE_MAPPING:
        return MARC_LANGUAGE_MAPPING[clean_code], "detected"

    # No mapping found - fall back to English
    return "eng", "unknown_code"
