# marc_pd_tool/shared/utils/marc_utilities.py

"""MARC data processing utilities and constants"""

# Standard library imports
from logging import getLogger

# Local imports
from marc_pd_tool.core.domain.enums import CountryClassification

logger = getLogger(__name__)

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


def _repair_country_code(country_code: str) -> str:
    """Attempt to repair common malformed country codes

    Args:
        country_code: Raw country code from MARC 008 field

    Returns:
        Repaired country code, or original if no repair possible
    """
    if not country_code:
        return country_code

    # Common repairs for encoding issues
    # Only repair patterns that clearly indicate missing data
    repairs = {
        # Mixed pipe and space patterns indicate missing data - treat as empty
        "| |": "",
        "|| ": "",
        " ||": "",
        # Common encoding corruption patterns could go here
        # Add more as patterns are discovered
    }

    # Note: "|||" is preserved as-is since it might be a valid malformed code
    # rather than indicating missing data

    # Check for exact match repairs
    if country_code in repairs:
        repaired = repairs[country_code]
        if repaired != country_code:
            logger.debug(f"Repaired country code '{country_code}' -> '{repaired}'")
        return repaired

    # Return the country code as-is - let the classification logic handle it
    # This preserves malformed codes for analysis while classifying them as UNKNOWN
    return country_code


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

    # Attempt to repair common malformed country codes
    country_code = _repair_country_code(country_code)

    # Check if repair resulted in empty code
    if not country_code:
        return "", CountryClassification.UNKNOWN

    # Check if this is a valid country code format (1-3 alphabetic characters)
    is_valid_format = (
        1 <= len(country_code) <= 3
        and country_code.isalpha()
        and not any(
            c in country_code
            for c in ["|", "-", "/", "0", "1", "2", "3", "4", "5", "6", "7", "8", "9"]
        )
    )

    if not is_valid_format:
        # Malformed code - preserve it but classify as UNKNOWN
        logger.debug(f"Malformed country code detected: '{country_code}' - classifying as UNKNOWN")
        return country_code, CountryClassification.UNKNOWN

    # Valid format - check against official US codes
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
