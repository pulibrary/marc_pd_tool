"""Publication data model for MARC and Copyright entries"""

# Standard library imports
from dataclasses import dataclass
from re import search
from typing import Dict
from typing import List
from typing import Optional

# Local imports
from marc_pd_tool.data.enums import CopyrightStatus
from marc_pd_tool.data.enums import CountryClassification
from marc_pd_tool.utils.text_utils import normalize_text


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
    matched_publisher: str = ""  # Source publisher
    publisher_score: float = 0.0  # Publisher similarity score


class Publication:
    __slots__ = (
        "original_title",
        "original_author",
        "original_main_author",
        "pub_date",
        "original_publisher",
        "original_place",
        "original_edition",
        "language_code",
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
        author: Optional[str] = None,
        main_author: Optional[str] = None,
        pub_date: Optional[str] = None,
        publisher: Optional[str] = None,
        place: Optional[str] = None,
        edition: Optional[str] = None,
        language_code: Optional[str] = None,
        source: Optional[str] = None,
        source_id: Optional[str] = None,
        country_code: Optional[str] = None,
        country_classification: CountryClassification = CountryClassification.UNKNOWN,
        full_text: Optional[str] = None,
    ):
        # Store original values, using None for missing data instead of empty strings
        self.original_title = title
        self.original_author = author if author else None
        self.original_main_author = main_author if main_author else None
        self.pub_date = pub_date if pub_date else None
        self.original_publisher = publisher if publisher else None
        self.original_place = place if place else None
        self.original_edition = edition if edition else None
        self.language_code = language_code.lower() if language_code else None
        self.source = source if source else None
        self.source_id = source_id if source_id else None
        self.full_text = full_text if full_text else None

        # Extract year
        self.year = self.extract_year()

        # Enhanced fields for new algorithm
        self.country_code = country_code if country_code else None
        self.country_classification = country_classification

        # Match tracking - single best match only
        self.registration_match: Optional[MatchResult] = None
        self.renewal_match: Optional[MatchResult] = None

        # Generic title detection info (populated during matching)
        self.generic_title_detected = False
        self.generic_detection_reason = "none"
        self.registration_generic_title = False
        self.renewal_generic_title = False

        # Final status
        self.copyright_status = CopyrightStatus.COUNTRY_UNKNOWN

        # Initialize cached normalized text fields (computed lazily)
        self._cached_title = None
        self._cached_author = None
        self._cached_main_author = None
        self._cached_publisher = None
        self._cached_place = None
        self._cached_edition = None

    # Properties for normalized text fields (cached after first access)
    @property
    def title(self) -> str:
        """Normalized title for matching"""
        if self._cached_title is None:
            self._cached_title = normalize_text(self.original_title) if self.original_title else ""
        return self._cached_title

    @property
    def author(self) -> str:
        """Normalized author for matching"""
        if self._cached_author is None:
            self._cached_author = (
                normalize_text(self.original_author) if self.original_author else ""
            )
        return self._cached_author

    @property
    def main_author(self) -> str:
        """Normalized main author for matching"""
        if self._cached_main_author is None:
            self._cached_main_author = (
                normalize_text(self.original_main_author) if self.original_main_author else ""
            )
        return self._cached_main_author

    @property
    def publisher(self) -> str:
        """Normalized publisher for matching"""
        if self._cached_publisher is None:
            self._cached_publisher = (
                normalize_text(self.original_publisher) if self.original_publisher else ""
            )
        return self._cached_publisher

    @property
    def place(self) -> str:
        """Normalized place for matching"""
        if self._cached_place is None:
            self._cached_place = normalize_text(self.original_place) if self.original_place else ""
        return self._cached_place

    @property
    def edition(self) -> str:
        """Normalized edition for matching"""
        if self._cached_edition is None:
            self._cached_edition = (
                normalize_text(self.original_edition) if self.original_edition else ""
            )
        return self._cached_edition

    def extract_year(self) -> Optional[int]:
        if not self.pub_date:
            return None
        # Expanded to handle historical publications from 1800s onward
        year_match = search(r"\b(18|19|20)\d{2}\b", self.pub_date)
        if year_match:
            return int(year_match.group())
        return None

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

        if self.country_classification == CountryClassification.US:
            # Special rule for US works published 1930-1963
            if self.year and 1930 <= self.year <= 1963:
                if has_reg and not has_ren:
                    # US works 1930-1963 with registration but no renewal are PD
                    self.copyright_status = CopyrightStatus.PD_NO_RENEWAL
                elif has_ren:
                    # US works 1930-1963 that were renewed are likely still copyrighted
                    self.copyright_status = CopyrightStatus.IN_COPYRIGHT
                else:
                    # US works 1930-1963 with no registration/renewal need verification
                    self.copyright_status = CopyrightStatus.PD_DATE_VERIFY
            else:
                # General US records logic for other years
                if has_reg and not has_ren:
                    self.copyright_status = CopyrightStatus.PD_DATE_VERIFY
                elif has_ren and not has_reg:
                    self.copyright_status = CopyrightStatus.IN_COPYRIGHT
                elif not has_reg and not has_ren:
                    self.copyright_status = CopyrightStatus.PD_DATE_VERIFY
                else:  # has both
                    self.copyright_status = CopyrightStatus.IN_COPYRIGHT

        elif self.country_classification == CountryClassification.NON_US:
            # Non-US records logic
            if has_reg or has_ren:
                self.copyright_status = CopyrightStatus.RESEARCH_US_STATUS
            else:
                self.copyright_status = CopyrightStatus.RESEARCH_US_ONLY_PD
        else:
            # Unknown country - still track matches but can't determine status
            self.copyright_status = CopyrightStatus.COUNTRY_UNKNOWN

        return self.copyright_status

    @staticmethod
    def normalize_text(text: str) -> str:
        """Static method for tests that expect this interface"""
        return normalize_text(text)

    def __getstate__(self):
        """Support for pickle serialization with __slots__"""
        return {slot: getattr(self, slot, None) for slot in self.__slots__}

    def __setstate__(self, state):
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

    def to_dict(self) -> Dict:
        return {
            "title": self.original_title,
            "author": self.original_author,
            "main_author": self.original_main_author,
            "pub_date": self.pub_date,
            "publisher": self.original_publisher,
            "place": self.original_place,
            "edition": self.original_edition,
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
