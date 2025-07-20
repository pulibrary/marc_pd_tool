"""Publication data model for MARC and Copyright entries"""

# Standard library imports
from dataclasses import dataclass
from re import search
from re import sub
from typing import Dict
from typing import List
from typing import Optional

# Local imports
from marc_pd_tool.enums import CopyrightStatus
from marc_pd_tool.enums import CountryClassification


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
    matched_date: str = ""  # Source publication/registration date
    matched_publisher: str = ""  # Source publisher
    publisher_score: float = 0.0  # Publisher similarity score


class Publication:
    def __init__(
        self,
        title: str,
        author: str = "",
        main_author: str = "",
        pub_date: str = "",
        publisher: str = "",
        place: str = "",
        edition: str = "",
        part_number: str = "",
        part_name: str = "",
        language_code: str = "",
        source: str = "",
        source_id: str = "",
        country_code: str = "",
        country_classification: CountryClassification = CountryClassification.UNKNOWN,
        full_text: str = "",
    ):
        self.title = self.normalize_text(title)
        self.author = self.normalize_text(author)
        self.main_author = self.normalize_text(main_author)
        self.pub_date = pub_date
        self.publisher = self.normalize_text(publisher)
        self.place = self.normalize_text(place)
        self.edition = self.normalize_text(edition)
        self.part_number = self.normalize_text(part_number)
        self.part_name = self.normalize_text(part_name)
        self.language_code = language_code.lower() if language_code else ""
        self.source = source
        self.source_id = source_id
        self.full_text = full_text  # Store original full_text for fuzzy matching

        # Store original values
        self.original_title = title
        self.original_author = author
        self.original_main_author = main_author
        self.original_publisher = publisher
        self.original_place = place
        self.original_edition = edition
        self.original_part_number = part_number
        self.original_part_name = part_name

        # Extract year
        self.year = self.extract_year()

        # Enhanced fields for new algorithm
        self.country_code = country_code
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

    @property
    def full_title(self) -> str:
        """Construct full title including part number and part name"""
        parts = [self.original_title]
        
        if self.original_part_number:
            parts.append(f"Part {self.original_part_number}")
        
        if self.original_part_name:
            parts.append(self.original_part_name)
        
        return ". ".join(parts)

    @property
    def full_title_normalized(self) -> str:
        """Normalized version of full title for matching"""
        return self.normalize_text(self.full_title)

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

    def to_dict(self) -> Dict:
        return {
            "title": self.original_title,
            "author": self.original_author,
            "main_author": self.original_main_author,
            "pub_date": self.pub_date,
            "publisher": self.original_publisher,
            "place": self.original_place,
            "edition": self.original_edition,
            "part_number": self.original_part_number,
            "part_name": self.original_part_name,
            "full_title": self.full_title,
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
