"""MARC data processing utilities and constants"""

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
