# marc_pd_tool/data/publication.py

"""Publication data model for MARC and Copyright entries"""

# Standard library imports
from dataclasses import dataclass

# Local imports
from marc_pd_tool.data.enums import CopyrightStatus
from marc_pd_tool.data.enums import CountryClassification
from marc_pd_tool.data.enums import MatchType
from marc_pd_tool.utils.marc_utilities import extract_language_from_marc
from marc_pd_tool.utils.text_utils import extract_year
from marc_pd_tool.utils.text_utils import normalize_lccn
from marc_pd_tool.utils.text_utils import normalize_text_comprehensive
from marc_pd_tool.utils.types import JSONDict


@dataclass(slots=True)
class MatchResult:
    """Represents a match between MARC record and copyright/renewal data"""

    matched_title: str
    matched_author: str
    similarity_score: float
    title_score: float
    author_score: float
    year_difference: int
    source_id: str
    source_type: str
    matched_date: str = ""  # Source publication/registration date
    matched_publisher: str | None = None  # Source publisher
    publisher_score: float = 0.0  # Publisher similarity score
    match_type: MatchType = (
        MatchType.SIMILARITY
    )  # Type of match (LCCN, SIMILARITY, or BRUTE_FORCE_WITHOUT_YEAR)


class Publication:
    __slots__ = (
        "original_title",
        "original_author",
        "original_main_author",
        "pub_date",
        "original_publisher",
        "original_place",
        "original_edition",
        "lccn",
        "normalized_lccn",
        "language_code",
        "language_detection_status",
        "source",
        "source_id",
        "full_text",
        "year",
        "country_code",
        "country_classification",
        "registration_match",
        "renewal_match",
        "generic_title_detected",
        "generic_detection_reason",
        "registration_generic_title",
        "renewal_generic_title",
        "copyright_status",
        "_cached_title",
        "_cached_author",
        "_cached_main_author",
        "_cached_publisher",
        "_cached_place",
        "_cached_edition",
    )

    def __init__(
        self,
        title: str,
        author: str | None = None,
        main_author: str | None = None,
        pub_date: str | None = None,
        publisher: str | None = None,
        place: str | None = None,
        edition: str | None = None,
        lccn: str | None = None,
        language_code: str | None = None,
        source: str | None = None,
        source_id: str | None = None,
        country_code: str | None = None,
        country_classification: CountryClassification = CountryClassification.UNKNOWN,
        full_text: str | None = None,
    ):
        # Store original values, using None for missing data instead of empty strings
        self.original_title = title
        self.original_author = author if author else None
        self.original_main_author = main_author if main_author else None
        self.pub_date = pub_date if pub_date else None
        self.original_publisher = publisher if publisher else None
        self.original_place = place if place else None
        self.original_edition = edition if edition else None
        self.lccn = lccn if lccn else None

        # Normalize LCCN if provided
        if self.lccn:
            self.normalized_lccn = normalize_lccn(self.lccn)
        else:
            self.normalized_lccn = ""

        # Process language code using MARC language mapping
        if language_code:
            self.language_code, self.language_detection_status = extract_language_from_marc(
                language_code
            )
        else:
            self.language_code = "eng"
            self.language_detection_status = "fallback_english"

        self.source = source if source else None
        self.source_id = source_id if source_id else None
        self.full_text = full_text if full_text else None

        # Extract year
        self.year = self.extract_year()

        # Enhanced fields for new algorithm
        self.country_code = country_code if country_code else None
        self.country_classification = country_classification

        # Match tracking - single best match only
        self.registration_match: MatchResult | None = None
        self.renewal_match: MatchResult | None = None

        # Generic title detection info (populated during matching)
        self.generic_title_detected = False
        self.generic_detection_reason = "none"
        self.registration_generic_title = False
        self.renewal_generic_title = False

        # Final status
        self.copyright_status = CopyrightStatus.COUNTRY_UNKNOWN

        # Initialize cached normalized text fields (computed lazily)
        self._cached_title: str | None = None
        self._cached_author: str | None = None
        self._cached_main_author: str | None = None
        self._cached_publisher: str | None = None
        self._cached_place: str | None = None
        self._cached_edition: str | None = None

    # Properties for normalized text fields (cached after first access)
    @property
    def title(self) -> str:
        """Normalized title for matching"""
        if self._cached_title is None:
            self._cached_title = (
                normalize_text_comprehensive(self.original_title) if self.original_title else ""
            )
        return self._cached_title

    @property
    def author(self) -> str:
        """Normalized author for matching"""
        if self._cached_author is None:
            self._cached_author = (
                normalize_text_comprehensive(self.original_author) if self.original_author else ""
            )
        return self._cached_author

    @property
    def main_author(self) -> str:
        """Normalized main author for matching"""
        if self._cached_main_author is None:
            self._cached_main_author = (
                normalize_text_comprehensive(self.original_main_author)
                if self.original_main_author
                else ""
            )
        return self._cached_main_author

    @property
    def publisher(self) -> str:
        """Normalized publisher for matching"""
        if self._cached_publisher is None:
            self._cached_publisher = (
                normalize_text_comprehensive(self.original_publisher)
                if self.original_publisher
                else ""
            )
        return self._cached_publisher

    @property
    def place(self) -> str:
        """Normalized place for matching"""
        if self._cached_place is None:
            self._cached_place = (
                normalize_text_comprehensive(self.original_place) if self.original_place else ""
            )
        return self._cached_place

    @property
    def edition(self) -> str:
        """Normalized edition for matching"""
        if self._cached_edition is None:
            self._cached_edition = (
                normalize_text_comprehensive(self.original_edition) if self.original_edition else ""
            )
        return self._cached_edition

    def extract_year(self) -> int | None:
        """Extract year from publication date using centralized extraction logic"""
        return extract_year(self.pub_date) if self.pub_date else None

    def set_registration_match(self, match: MatchResult) -> None:
        """Set the best registration match"""
        match.source_type = "registration"
        self.registration_match = match

    def set_renewal_match(self, match: MatchResult) -> None:
        """Set the best renewal match"""
        match.source_type = "renewal"
        self.renewal_match = match

    def has_registration_match(self) -> bool:
        """Check if record has a registration match"""
        return self.registration_match is not None

    def has_renewal_match(self) -> bool:
        """Check if record has a renewal match"""
        return self.renewal_match is not None

    def determine_copyright_status(self) -> CopyrightStatus:
        """Determine final copyright status based on matches, country, and publication year"""
        has_reg = self.has_registration_match()
        has_ren = self.has_renewal_match()

        match (self.country_classification, self.year, has_reg, has_ren):
            # US works 1930-1963 with specific registration/renewal patterns
            case (CountryClassification.US, year, True, False) if year and 1930 <= year <= 1963:
                # US works 1930-1963 with registration but no renewal are PD
                self.copyright_status = CopyrightStatus.PD_NO_RENEWAL
            case (CountryClassification.US, year, _, True) if year and 1930 <= year <= 1963:
                # US works 1930-1963 that were renewed are likely still copyrighted
                self.copyright_status = CopyrightStatus.IN_COPYRIGHT
            case (CountryClassification.US, year, False, False) if year and 1930 <= year <= 1963:
                # US works 1930-1963 with no registration/renewal need verification
                self.copyright_status = CopyrightStatus.PD_DATE_VERIFY

            # General US records for other years
            case (CountryClassification.US, _, True, False):
                self.copyright_status = CopyrightStatus.PD_DATE_VERIFY
            case (CountryClassification.US, _, False, True):
                self.copyright_status = CopyrightStatus.IN_COPYRIGHT
            case (CountryClassification.US, _, False, False):
                self.copyright_status = CopyrightStatus.PD_DATE_VERIFY
            case (CountryClassification.US, _, True, True):
                self.copyright_status = CopyrightStatus.IN_COPYRIGHT

            # Non-US records
            case (CountryClassification.NON_US, _, _, _) if has_reg or has_ren:
                self.copyright_status = CopyrightStatus.RESEARCH_US_STATUS
            case (CountryClassification.NON_US, _, _, _):
                self.copyright_status = CopyrightStatus.RESEARCH_US_ONLY_PD

            # Unknown country
            case _:
                # Unknown country - still track matches but can't determine status
                self.copyright_status = CopyrightStatus.COUNTRY_UNKNOWN

        return self.copyright_status

    def __getstate__(self) -> JSONDict:
        """Support for pickle serialization with __slots__"""
        # Use type: ignore for getattr with default None to avoid Any propagation
        return {slot: getattr(self, slot, None) for slot in self.__slots__}

    def __setstate__(self, state: JSONDict) -> None:
        """Support for pickle deserialization with __slots__"""
        for slot, value in state.items():
            setattr(self, slot, value)

        # Clear cached properties - they'll be regenerated lazily
        for attr in [
            "_cached_title",
            "_cached_author",
            "_cached_main_author",
            "_cached_publisher",
            "_cached_place",
            "_cached_edition",
        ]:
            setattr(self, attr, None)

    def to_dict(self) -> dict[str, str | int | None | dict[str, str | float | int]]:
        return {
            "title": self.original_title,
            "author": self.original_author,
            "main_author": self.original_main_author,
            "pub_date": self.pub_date,
            "publisher": self.original_publisher,
            "place": self.original_place,
            "edition": self.original_edition,
            "lccn": self.lccn,
            "normalized_lccn": self.normalized_lccn,
            "language_code": self.language_code,
            "source": self.source,
            "source_id": self.source_id,
            "year": self.year,
            "country_code": self.country_code,
            "country_classification": self.country_classification.value,
            "copyright_status": self.copyright_status.value,
            "full_text": self.full_text,
            "registration_match": (
                {
                    "matched_title": self.registration_match.matched_title,
                    "matched_author": self.registration_match.matched_author,
                    "similarity_score": self.registration_match.similarity_score,
                    "title_score": self.registration_match.title_score,
                    "author_score": self.registration_match.author_score,
                    "year_difference": self.registration_match.year_difference,
                    "source_id": self.registration_match.source_id,
                }
                if self.registration_match
                else None
            ),
            "renewal_match": (
                {
                    "matched_title": self.renewal_match.matched_title,
                    "matched_author": self.renewal_match.matched_author,
                    "similarity_score": self.renewal_match.similarity_score,
                    "title_score": self.renewal_match.title_score,
                    "author_score": self.renewal_match.author_score,
                    "year_difference": self.renewal_match.year_difference,
                    "source_id": self.renewal_match.source_id,
                }
                if self.renewal_match
                else None
            ),
        }
