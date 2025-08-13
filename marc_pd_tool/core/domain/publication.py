# marc_pd_tool/core/domain/publication.py

"""Core Publication domain entity"""

# Local imports
from marc_pd_tool.core.domain.enums import CopyrightStatus
from marc_pd_tool.core.domain.enums import CopyrightStatusRule
from marc_pd_tool.core.domain.enums import CountryClassification
from marc_pd_tool.core.domain.match_result import MatchResult


class Publication:
    """Core domain entity representing a publication

    This is a pure data class holding publication information.
    Business logic for copyright determination is in separate modules.
    """

    __slots__ = (
        # Original data fields
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
        # Match tracking
        "_registration_match",
        "_renewal_match",
        # Generic title detection
        "generic_title_detected",
        "generic_detection_reason",
        "registration_generic_title",
        "renewal_generic_title",
        # Copyright status
        "copyright_status",
        "status_rule",
        "sort_score",
        "data_completeness",
        # Cached normalized fields
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
        normalized_lccn: str = "",
        language_code: str | None = None,
        language_detection_status: str = "fallback_english",
        source: str | None = None,
        source_id: str | None = None,
        country_code: str | None = None,
        country_classification: CountryClassification = CountryClassification.UNKNOWN,
        full_text: str | None = None,
        year: int | None = None,
    ):
        # Store original values
        self.original_title = title
        self.original_author = author if author else None
        self.original_main_author = main_author if main_author else None
        self.pub_date = pub_date if pub_date else None
        self.original_publisher = publisher if publisher else None
        self.original_place = place if place else None
        self.original_edition = edition if edition else None
        self.lccn = lccn if lccn else None
        # Normalize LCCN if provided, otherwise use the explicit normalized_lccn parameter
        if lccn and not normalized_lccn:
            # Local imports
            from marc_pd_tool.shared.utils.text_utils import normalize_lccn

            self.normalized_lccn = normalize_lccn(lccn)
        else:
            self.normalized_lccn = normalized_lccn

        # Language and source info
        # Process language code through MARC language mapping
        if language_code is not None:
            # Local imports
            from marc_pd_tool.shared.utils.marc_utilities import (
                extract_language_from_marc,
            )

            self.language_code, detected_status = extract_language_from_marc(language_code)
            # Only use the provided language_detection_status if it was explicitly set
            # (i.e., not the default "fallback_english")
            # This allows extract_language_from_marc to set the correct status
            self.language_detection_status = detected_status
        else:
            self.language_code = "eng"
            self.language_detection_status = language_detection_status
        self.source = source if source else None
        self.source_id = source_id if source_id else None
        self.full_text = full_text if full_text else None

        # Year and country
        # Extract year from pub_date if not explicitly provided
        if year is not None:
            self.year = year
        else:
            self.year = self.extract_year()
        self.country_code = country_code if country_code else None
        self.country_classification = country_classification

        # Match tracking - single best match only
        self._registration_match: MatchResult | None = None
        self._renewal_match: MatchResult | None = None

        # Generic title detection info
        self.generic_title_detected = False
        self.generic_detection_reason = "none"
        self.registration_generic_title = False
        self.renewal_generic_title = False

        # Final status
        self.copyright_status = CopyrightStatus.COUNTRY_UNKNOWN_NO_MATCH.value
        self.status_rule: CopyrightStatusRule | None = None
        self.sort_score: float = 0.0
        self.data_completeness: list[str] = []

        # Initialize cached normalized text fields
        self._cached_title: str | None = None
        self._cached_author: str | None = None
        self._cached_main_author: str | None = None
        self._cached_publisher: str | None = None
        self._cached_place: str | None = None
        self._cached_edition: str | None = None

    @property
    def registration_match(self) -> MatchResult | None:
        """Get the registration match"""
        return self._registration_match

    @registration_match.setter
    def registration_match(self, match: MatchResult | None) -> None:
        """Set the best registration match"""
        if match is not None:
            match.source_type = "registration"
        self._registration_match = match

    @property
    def renewal_match(self) -> MatchResult | None:
        """Get the renewal match"""
        return self._renewal_match

    @renewal_match.setter
    def renewal_match(self, match: MatchResult | None) -> None:
        """Set the best renewal match"""
        if match is not None:
            match.source_type = "renewal"
        self._renewal_match = match

    def has_registration_match(self) -> bool:
        """Check if record has a registration match"""
        return self._registration_match is not None

    def has_renewal_match(self) -> bool:
        """Check if record has a renewal match"""
        return self._renewal_match is not None

    # Normalized property accessors (lazy evaluation)
    @property
    def title(self) -> str:
        """Get title text with minimal cleanup only"""
        if self._cached_title is None:
            # Only do minimal cleanup - the full normalization happens in SimilarityCalculator
            if self.original_title:
                # Standard library imports
                import re

                # Local imports
                from marc_pd_tool.shared.utils.text_utils import (
                    remove_bracketed_content,
                )

                # Remove bracketed content like [microform]
                cleaned = remove_bracketed_content(self.original_title)
                # Just normalize whitespace
                self._cached_title = re.sub(r"\s+", " ", cleaned).strip()
            else:
                self._cached_title = ""
        return self._cached_title

    @property
    def author(self) -> str:
        """Get author text with minimal cleanup only"""
        if self._cached_author is None:
            # Only do minimal cleanup - the full normalization happens in SimilarityCalculator
            if self.original_author:
                # Just normalize whitespace
                # Standard library imports
                import re

                self._cached_author = re.sub(r"\s+", " ", self.original_author).strip()
            else:
                self._cached_author = ""
        return self._cached_author

    @property
    def main_author(self) -> str:
        """Get main author text (with minimal cleanup only)"""
        if self._cached_main_author is None:
            # Only do minimal cleanup - the full normalization happens in SimilarityCalculator
            if self.original_main_author:
                # Just normalize whitespace
                # Standard library imports
                import re

                self._cached_main_author = re.sub(r"\s+", " ", self.original_main_author).strip()
            else:
                self._cached_main_author = ""
        return self._cached_main_author

    @property
    def publisher(self) -> str:
        """Get publisher text (with minimal cleanup only)"""
        if self._cached_publisher is None:
            # Only do minimal cleanup - the full normalization happens in SimilarityCalculator
            if self.original_publisher:
                # Just normalize whitespace
                # Standard library imports
                import re

                self._cached_publisher = re.sub(r"\s+", " ", self.original_publisher).strip()
            else:
                self._cached_publisher = ""
        return self._cached_publisher

    @property
    def place(self) -> str:
        """Get place text (with minimal cleanup only)"""
        if self._cached_place is None:
            # Only do minimal cleanup - the full normalization happens in SimilarityCalculator
            if self.original_place:
                # Just normalize whitespace
                # Standard library imports
                import re

                self._cached_place = re.sub(r"\s+", " ", self.original_place).strip()
            else:
                self._cached_place = ""
        return self._cached_place

    @property
    def edition(self) -> str:
        """Get edition text (with minimal cleanup only)"""
        if self._cached_edition is None:
            # Only do minimal cleanup - the full normalization happens in SimilarityCalculator
            if self.original_edition:
                # Just normalize whitespace
                # Standard library imports
                import re

                self._cached_edition = re.sub(r"\s+", " ", self.original_edition).strip()
            else:
                self._cached_edition = ""
        return self._cached_edition

    def extract_year(self) -> int | None:
        """Extract year from publication date using centralized extraction logic"""
        # Local imports
        from marc_pd_tool.shared.utils.text_utils import extract_year

        return extract_year(self.pub_date) if self.pub_date else None

    def determine_copyright_status(
        self, copyright_expiration_year: int | None = None, max_data_year: int | None = None
    ) -> str:
        """Determine final copyright status based on matches, country, and publication year

        Args:
            copyright_expiration_year: Year before which works expire (typically current_year - 96)
            max_data_year: Maximum year of available copyright/renewal data (e.g., 1991)

        Returns:
            String status that may be dynamically generated (e.g., "US_PRE_1929")
        """
        # Local imports
        from marc_pd_tool.core.domain.copyright_logic import determine_copyright_status

        return determine_copyright_status(self, copyright_expiration_year, max_data_year)

    def calculate_sort_score(self) -> float:
        """Calculate sort score for quality-based ordering

        Higher scores = better matches:
        - LCCN matches = 1000 points
        - Both reg + renewal = average of scores
        - Registration only = reg score
        - Renewal only = ren score * 0.9
        - No matches = 0
        """
        # Local imports
        from marc_pd_tool.core.domain.enums import MatchType

        # LCCN matches get highest priority
        if self.registration_match and self.registration_match.match_type == MatchType.LCCN:
            self.sort_score = 1000.0
        elif self.renewal_match and self.renewal_match.match_type == MatchType.LCCN:
            self.sort_score = 1000.0
        # Both registration and renewal
        elif self.registration_match and self.renewal_match:
            self.sort_score = (
                self.registration_match.similarity_score + self.renewal_match.similarity_score
            ) / 2.0
        # Registration only
        elif self.registration_match:
            self.sort_score = self.registration_match.similarity_score
        # Renewal only (slightly lower weight)
        elif self.renewal_match:
            self.sort_score = self.renewal_match.similarity_score * 0.9
        # No matches
        else:
            self.sort_score = 0.0

        return self.sort_score

    def check_data_completeness(self) -> list[str]:
        """Check for data quality issues and populate data_completeness list"""
        self.data_completeness = []

        if not self.year:
            self.data_completeness.append("missing_year")
        if not self.original_publisher:
            self.data_completeness.append("missing_publisher")
        if not self.original_author and not self.original_main_author:
            self.data_completeness.append("missing_author")
        if self.generic_title_detected:
            self.data_completeness.append("generic_title")
        if not self.country_code or self.country_classification == CountryClassification.UNKNOWN:
            self.data_completeness.append("unknown_country")

        return self.data_completeness

    def __getstate__(self) -> dict[str, object]:
        """Support for pickle serialization with __slots__"""
        return {slot: getattr(self, slot, None) for slot in self.__slots__}

    def __setstate__(self, state: dict[str, object]) -> None:
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
        """Convert to dictionary representation"""
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
            "copyright_status": self.copyright_status,
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
