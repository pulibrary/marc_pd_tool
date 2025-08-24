# marc_pd_tool/application/processing/derived_work_detector.py

"""Detector for derived works (indexes, bibliographies, supplements) to prevent false positives"""

# Standard library imports
from re import IGNORECASE
from re import Pattern
from re import compile as re_compile

# Third party imports
from pydantic import BaseModel
from pydantic import Field

# Local imports
from marc_pd_tool.shared.utils.text_utils import normalize_unicode


class DerivedWorkInfo(BaseModel):
    """Information about detected derived work patterns"""

    is_derived: bool = Field(
        default=False, description="Whether a derived work pattern was detected"
    )
    pattern_matched: str = Field(default="", description="The pattern that matched")
    confidence: float = Field(default=0.0, description="Confidence level of detection (0-1)")
    language_hint: str = Field(
        default="", description="Language hint from pattern (e.g., 'eng', 'fre', 'ger')"
    )


class DerivedWorkDetector:
    """Detects derived works like indexes, bibliographies, and supplements

    These often cause false positives because they reference the original work
    in their titles but are distinct publications.
    """

    # English patterns
    ENGLISH_PATTERNS = [
        (r"^index\s+(to|of|for)\s+", 0.95, "index"),
        (r"^bibliography\s+(of|for|on)\s+", 0.95, "bibliography"),
        (r"^supplement\s+(to|for)\s+", 0.9, "supplement"),
        (r"^guide\s+(to|for)\s+", 0.8, "guide"),
        (r"^handbook\s+(of|for|on)\s+", 0.8, "handbook"),
        (r"^companion\s+(to|for)\s+", 0.85, "companion"),
        (r"^introduction\s+to\s+", 0.7, "introduction"),
        (r"^abstracts?\s+(of|from)\s+", 0.9, "abstract"),
        (r"^digest\s+(of|from)\s+", 0.85, "digest"),
        (r"^concordance\s+(to|of)\s+", 0.95, "concordance"),
        (r"^selected\s+(readings?|works?|papers?)\s+(from|of)\s+", 0.8, "selection"),
        (r"^excerpts?\s+(from|of)\s+", 0.85, "excerpt"),
        (r"\s+index$", 0.9, "index_suffix"),
        (r"\s+bibliography$", 0.9, "bibliography_suffix"),
        (r"\s+supplement$", 0.85, "supplement_suffix"),
    ]

    # French patterns (normalized forms)
    FRENCH_PATTERNS = [
        (r"^index\s+(de|des|du|pour)\s+", 0.95, "index"),
        (r"^bibliographie\s+(de|des|du|sur)\s+", 0.95, "bibliographie"),
        (r"^supplement\s+(au?|de|du|pour)\s+", 0.9, "supplement"),
        (r"^guide\s+(de|des|du|pour)\s+", 0.8, "guide"),
        (r"^manuel\s+(de|des|du)\s+", 0.8, "manuel"),
        (r"^introduction\s+a\s+", 0.7, "introduction"),
        (r"^abrege\s+(de|des|du)\s+", 0.85, "abrege"),
        (r"^extraits?\s+(de|des|du)\s+", 0.85, "extrait"),
        (r"^concordance\s+(de|des|du)\s+", 0.95, "concordance"),
        (r"\s+index$", 0.9, "index_suffix"),
        (r"\s+bibliographie$", 0.9, "bibliographie_suffix"),
    ]

    # German patterns (normalized forms without umlauts)
    GERMAN_PATTERNS = [
        (r"^index\s+(zu|von|fur)\s+", 0.95, "index"),
        (r"^register\s+(zu|von|fur)\s+", 0.95, "register"),
        (r"^bibliographie\s+(zu|von|uber)\s+", 0.95, "bibliographie"),
        (r"^erganzung\s+(zu|zur|zum|von)\s+", 0.9, "ergaenzung"),
        (r"^nachtrag\s+(zu|zur|zum|von)\s+", 0.9, "nachtrag"),
        (r"^handbuch\s+(der|des|zu|zur|zum|uber)\s+", 0.8, "handbuch"),
        (r"^einfuhrung\s+in\s+", 0.7, "einfuehrung"),
        (r"^auszuge?\s+(aus|von)\s+", 0.85, "auszug"),
        (r"^konkordanz\s+(zu|zur|zum|von)\s+", 0.95, "konkordanz"),
    ]

    # Spanish patterns (normalized forms)
    SPANISH_PATTERNS = [
        (r"^indice\s+(de|del|para)\s+", 0.95, "indice"),
        (r"^bibliografia\s+(de|del|sobre)\s+", 0.95, "bibliografia"),
        (r"^suplemento\s+(de|del|al?|para)\s+", 0.9, "suplemento"),
        (r"^guia\s+(de|del|para)\s+", 0.8, "guia"),
        (r"^manual\s+(de|del)\s+", 0.8, "manual"),
        (r"^introduccion\s+a\s+", 0.7, "introduccion"),
        (r"^extractos?\s+(de|del)\s+", 0.85, "extracto"),
        (r"^concordancia\s+(de|del)\s+", 0.95, "concordancia"),
    ]

    # Italian patterns (normalized forms)
    ITALIAN_PATTERNS = [
        (r"^indice\s+(di|del|per)\s+", 0.95, "indice"),
        (r"^bibliografia\s+(di|del|su)\s+", 0.95, "bibliografia"),
        (r"^supplemento\s+(di|del|al?|per)\s+", 0.9, "supplemento"),
        (r"^guida\s+(di|del|per|a)\s+", 0.8, "guida"),
        (r"^manuale\s+(di|del)\s+", 0.8, "manuale"),
        (r"^introduzione\s+a\s+", 0.7, "introduzione"),
        (r"^estratti?\s+(da|di|del)\s+", 0.85, "estratto"),
        (r"^concordanza\s+(di|del)\s+", 0.95, "concordanza"),
    ]

    def __init__(self) -> None:
        """Initialize the derived work detector with compiled patterns"""
        self.patterns: dict[str, list[tuple[Pattern[str], float, str]]] = {
            "eng": [
                (re_compile(p, IGNORECASE), conf, name) for p, conf, name in self.ENGLISH_PATTERNS
            ],
            "fre": [
                (re_compile(p, IGNORECASE), conf, name) for p, conf, name in self.FRENCH_PATTERNS
            ],
            "ger": [
                (re_compile(p, IGNORECASE), conf, name) for p, conf, name in self.GERMAN_PATTERNS
            ],
            "spa": [
                (re_compile(p, IGNORECASE), conf, name) for p, conf, name in self.SPANISH_PATTERNS
            ],
            "ita": [
                (re_compile(p, IGNORECASE), conf, name) for p, conf, name in self.ITALIAN_PATTERNS
            ],
        }

    def detect(
        self, marc_title: str, copyright_title: str, language: str = "eng"
    ) -> tuple[DerivedWorkInfo, DerivedWorkInfo]:
        """Check if either title appears to be a derived work

        Args:
            marc_title: Title from MARC record
            copyright_title: Title from copyright/renewal record
            language: Language code (eng, fre, ger, spa, ita)

        Returns:
            Tuple of (marc_info, copyright_info) with detection results
        """
        marc_info = self._check_single_title(marc_title, language)
        copyright_info = self._check_single_title(copyright_title, language)

        return marc_info, copyright_info

    def _check_single_title(self, title: str, language: str) -> DerivedWorkInfo:
        """Check a single title for derived work patterns

        Args:
            title: Title to check
            language: Language code

        Returns:
            DerivedWorkInfo with detection results
        """
        if not title:
            return DerivedWorkInfo()

        # Normalize the title for pattern matching
        normalized = normalize_unicode(title).lower().strip()

        # Get patterns for the specified language, fall back to English
        lang_patterns = self.patterns.get(language, self.patterns["eng"])

        # Check each pattern
        best_match = DerivedWorkInfo()
        for pattern, confidence, pattern_name in lang_patterns:
            if pattern.search(normalized):
                # If we find a higher confidence match, update
                if confidence > best_match.confidence:
                    best_match = DerivedWorkInfo(
                        is_derived=True,
                        pattern_matched=pattern_name,
                        confidence=confidence,
                        language_hint=language,
                    )

        # Also check English patterns if using a non-English language
        # (many academic works use English terms even in other languages)
        if language != "eng":
            for pattern, confidence, pattern_name in self.patterns["eng"]:
                if pattern.search(normalized):
                    # Apply slight penalty for cross-language match
                    adjusted_confidence = confidence * 0.9
                    if adjusted_confidence > best_match.confidence:
                        best_match = DerivedWorkInfo(
                            is_derived=True,
                            pattern_matched=f"{pattern_name}_eng",
                            confidence=adjusted_confidence,
                            language_hint="eng",
                        )

        return best_match

    def should_penalize_match(
        self, marc_derived: DerivedWorkInfo, copyright_derived: DerivedWorkInfo, base_score: float
    ) -> tuple[bool, float]:
        """Determine if a match should be penalized for derived work patterns

        Args:
            marc_derived: Derived work info for MARC title
            copyright_derived: Derived work info for copyright title
            base_score: The base similarity score

        Returns:
            Tuple of (should_penalize, adjusted_score)
        """
        # If neither is detected as derived, no penalty
        if not marc_derived.is_derived and not copyright_derived.is_derived:
            return False, base_score

        # If both are derived works of the same type, less penalty
        if marc_derived.is_derived and copyright_derived.is_derived:
            if marc_derived.pattern_matched == copyright_derived.pattern_matched:
                # Same type of derived work - might be legitimate
                # Apply small penalty based on confidence
                avg_confidence = (marc_derived.confidence + copyright_derived.confidence) / 2
                penalty_factor = 1.0 - (avg_confidence * 0.1)  # Max 10% penalty
                return True, base_score * penalty_factor
            else:
                # Different types of derived works - more suspicious
                # Apply moderate penalty
                avg_confidence = (marc_derived.confidence + copyright_derived.confidence) / 2
                penalty_factor = 1.0 - (avg_confidence * 0.3)  # Max 30% penalty
                return True, base_score * penalty_factor

        # One is derived, one isn't - most suspicious
        # Apply strong penalty based on confidence of the derived work
        if marc_derived.is_derived:
            penalty_factor = 1.0 - (marc_derived.confidence * 0.5)  # Max 50% penalty
        else:
            penalty_factor = 1.0 - (copyright_derived.confidence * 0.5)  # Max 50% penalty

        return True, base_score * penalty_factor

    def get_penalty_reason(
        self, marc_derived: DerivedWorkInfo, copyright_derived: DerivedWorkInfo
    ) -> str:
        """Get a human-readable reason for penalty

        Args:
            marc_derived: Derived work info for MARC title
            copyright_derived: Derived work info for copyright title

        Returns:
            Description of why penalty was applied
        """
        if not marc_derived.is_derived and not copyright_derived.is_derived:
            return "No derived work detected"

        if marc_derived.is_derived and copyright_derived.is_derived:
            if marc_derived.pattern_matched == copyright_derived.pattern_matched:
                return f"Both are {marc_derived.pattern_matched} works"
            else:
                return f"MARC is {marc_derived.pattern_matched}, copyright is {copyright_derived.pattern_matched}"

        if marc_derived.is_derived:
            return f"MARC appears to be {marc_derived.pattern_matched} (confidence: {marc_derived.confidence:.1%})"
        else:
            return f"Copyright appears to be {copyright_derived.pattern_matched} (confidence: {copyright_derived.confidence:.1%})"
