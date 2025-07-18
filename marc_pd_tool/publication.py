"""Publication data model for MARC and Copyright entries"""

# Standard library imports
from dataclasses import dataclass
from re import search
from re import sub
from typing import Dict
from typing import List
from typing import Optional

# Local imports
from marc_pd_tool.enums import AuthorType
from marc_pd_tool.enums import CopyrightStatus
from marc_pd_tool.enums import CountryClassification

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


@dataclass
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


class Publication:
    def __init__(
        self,
        title: str,
        author: str = "",
        pub_date: str = "",
        publisher: str = "",
        place: str = "",
        source: str = "",
        source_id: str = "",
        country_code: str = "",
        country_classification: CountryClassification = CountryClassification.UNKNOWN,
        author_type: AuthorType = AuthorType.UNKNOWN,
    ):
        self.title = self.normalize_text(title)
        self.author = self.normalize_text(author)
        self.pub_date = pub_date
        self.publisher = self.normalize_text(publisher)
        self.place = self.normalize_text(place)
        self.source = source
        self.source_id = source_id

        # Store original values
        self.original_title = title
        self.original_author = author
        self.original_publisher = publisher
        self.original_place = place

        # Extract year
        self.year = self.extract_year()

        # Enhanced fields for new algorithm
        self.country_code = country_code
        self.country_classification = country_classification
        self.author_type = author_type

        # Match tracking - single best match only
        self.registration_match: Optional[MatchResult] = None
        self.renewal_match: Optional[MatchResult] = None

        # Final status
        self.copyright_status = CopyrightStatus.COUNTRY_UNKNOWN

    @staticmethod
    def normalize_text(text: str) -> str:
        if not text:
            return ""
        text = sub(r"[^\w\s]", " ", text)
        text = sub(r"\s+", " ", text)
        return text.strip().lower()

    def extract_year(self) -> Optional[int]:
        if not self.pub_date:
            return None
        year_match = search(r"\b(19|20)\d{2}\b", self.pub_date)
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
        """Determine final copyright status based on matches and country"""
        has_reg = self.has_registration_match()
        has_ren = self.has_renewal_match()

        if self.country_classification == CountryClassification.US:
            # US records logic
            if has_reg and not has_ren:
                self.copyright_status = CopyrightStatus.POTENTIALLY_PD_DATE_VERIFY
            elif has_ren and not has_reg:
                self.copyright_status = CopyrightStatus.POTENTIALLY_IN_COPYRIGHT
            elif not has_reg and not has_ren:
                self.copyright_status = CopyrightStatus.POTENTIALLY_PD_DATE_VERIFY
            else:  # has both
                self.copyright_status = CopyrightStatus.POTENTIALLY_IN_COPYRIGHT

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

    def to_dict(self) -> Dict:
        return {
            "title": self.original_title,
            "author": self.original_author,
            "pub_date": self.pub_date,
            "publisher": self.original_publisher,
            "place": self.original_place,
            "source": self.source,
            "source_id": self.source_id,
            "year": self.year,
            "country_code": self.country_code,
            "country_classification": self.country_classification.value,
            "copyright_status": self.copyright_status.value,
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
