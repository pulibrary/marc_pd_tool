# marc_pd_tool/core/domain/copyright_logic.py

"""Copyright status determination logic"""

# Standard library imports
from datetime import datetime

# Local imports
from marc_pd_tool.core.domain.enums import CopyrightStatus
from marc_pd_tool.core.domain.enums import CopyrightStatusRule
from marc_pd_tool.core.domain.enums import CountryClassification
from marc_pd_tool.core.domain.publication import Publication


def determine_copyright_status(
    publication: Publication,
    copyright_expiration_year: int | None = None,
    max_data_year: int | None = None,
) -> str:
    """Determine final copyright status based on matches, country, and publication year

    Args:
        publication: Publication to analyze
        copyright_expiration_year: Year before which works expire (typically current_year - 96)
        max_data_year: Maximum year of available copyright/renewal data (e.g., 1991)

    Returns:
        String status that may be dynamically generated (e.g., "US_PRE_1929")
    """
    has_reg = publication.has_registration_match()
    has_ren = publication.has_renewal_match()

    # Set defaults if not provided
    if copyright_expiration_year is None:
        copyright_expiration_year = datetime.now().year - 96

    if max_data_year is None:
        max_data_year = 1991  # Default based on current data

    # Check for pre-copyright expiration
    if publication.year and publication.year < copyright_expiration_year:
        if publication.country_classification == CountryClassification.US:
            publication.copyright_status = f"US_PRE_{copyright_expiration_year}"
            publication.status_rule = CopyrightStatusRule.US_PRE_COPYRIGHT_EXPIRATION
        elif publication.country_classification == CountryClassification.NON_US:
            country_suffix = f"_{publication.country_code}" if publication.country_code else ""
            publication.copyright_status = (
                f"FOREIGN_PRE_{copyright_expiration_year}{country_suffix}"
            )
            publication.status_rule = CopyrightStatusRule.FOREIGN_PRE_COPYRIGHT_EXPIRATION
        else:
            publication.copyright_status = f"COUNTRY_UNKNOWN_PRE_{copyright_expiration_year}"
            publication.status_rule = CopyrightStatusRule.US_PRE_COPYRIGHT_EXPIRATION
        return publication.copyright_status

    # Check if beyond our data range
    if publication.year and publication.year > max_data_year:
        publication.copyright_status = f"OUT_OF_DATA_RANGE_{max_data_year}"
        publication.status_rule = CopyrightStatusRule.OUT_OF_DATA_RANGE
        return publication.copyright_status

    # Main status determination logic
    match (publication.country_classification, publication.year, has_reg, has_ren):
        # US works in renewal period (copyright_expiration_year-1977)
        case (CountryClassification.US, year, True, False) if (
            year and copyright_expiration_year <= year <= 1977
        ):
            publication.copyright_status = CopyrightStatus.US_REGISTERED_NOT_RENEWED.value
            publication.status_rule = CopyrightStatusRule.US_RENEWAL_PERIOD_NOT_RENEWED
        case (CountryClassification.US, year, _, True) if (
            year and copyright_expiration_year <= year <= 1977
        ):
            publication.copyright_status = CopyrightStatus.US_RENEWED.value
            publication.status_rule = CopyrightStatusRule.US_RENEWAL_PERIOD_RENEWED
        case (CountryClassification.US, year, False, False) if (
            year and copyright_expiration_year <= year <= 1977
        ):
            publication.copyright_status = CopyrightStatus.US_NO_MATCH.value
            publication.status_rule = CopyrightStatusRule.US_RENEWAL_PERIOD_NO_MATCH

        # US records without year or outside renewal period
        case (CountryClassification.US, _, True, False):
            publication.copyright_status = CopyrightStatus.US_REGISTERED_NOT_RENEWED.value
            publication.status_rule = CopyrightStatusRule.US_REGISTERED_NO_RENEWAL
        case (CountryClassification.US, _, False, True):
            publication.copyright_status = CopyrightStatus.US_RENEWED.value
            publication.status_rule = CopyrightStatusRule.US_RENEWAL_FOUND
        case (CountryClassification.US, _, True, True):
            publication.copyright_status = CopyrightStatus.US_RENEWED.value
            publication.status_rule = CopyrightStatusRule.US_BOTH_REG_AND_RENEWAL
        case (CountryClassification.US, _, False, False):
            publication.copyright_status = CopyrightStatus.US_NO_MATCH.value
            publication.status_rule = CopyrightStatusRule.US_NO_MATCH

        # Foreign Works
        case (CountryClassification.NON_US, _, _, True):
            country_suffix = f"_{publication.country_code}" if publication.country_code else ""
            publication.copyright_status = (
                f"{CopyrightStatus.FOREIGN_RENEWED.value}{country_suffix}"
            )
            publication.status_rule = CopyrightStatusRule.FOREIGN_RENEWED
        case (CountryClassification.NON_US, _, True, False):
            country_suffix = f"_{publication.country_code}" if publication.country_code else ""
            publication.copyright_status = (
                f"{CopyrightStatus.FOREIGN_REGISTERED_NOT_RENEWED.value}{country_suffix}"
            )
            publication.status_rule = CopyrightStatusRule.FOREIGN_REGISTERED_NOT_RENEWED
        case (CountryClassification.NON_US, _, False, False):
            country_suffix = f"_{publication.country_code}" if publication.country_code else ""
            publication.copyright_status = (
                f"{CopyrightStatus.FOREIGN_NO_MATCH.value}{country_suffix}"
            )
            publication.status_rule = CopyrightStatusRule.FOREIGN_NO_MATCH

        # Unknown Country
        case (CountryClassification.UNKNOWN, _, _, True):
            publication.copyright_status = CopyrightStatus.COUNTRY_UNKNOWN_RENEWED.value
            publication.status_rule = CopyrightStatusRule.COUNTRY_UNKNOWN_RENEWED
        case (CountryClassification.UNKNOWN, _, True, False):
            publication.copyright_status = (
                CopyrightStatus.COUNTRY_UNKNOWN_REGISTERED_NOT_RENEWED.value
            )
            publication.status_rule = CopyrightStatusRule.COUNTRY_UNKNOWN_REGISTERED
        case (CountryClassification.UNKNOWN, _, False, False):
            publication.copyright_status = CopyrightStatus.COUNTRY_UNKNOWN_NO_MATCH.value
            publication.status_rule = CopyrightStatusRule.COUNTRY_UNKNOWN_NO_MATCH

    return publication.copyright_status
