# marc_pd_tool/application/processing/matching/_score_combiner.py

"""Score combination and weighting logic for matching"""

# Standard library imports
from logging import getLogger

# Local imports
from marc_pd_tool.application.processing.derived_work_detector import DerivedWorkInfo
from marc_pd_tool.core.types.json import JSONDict
from marc_pd_tool.infrastructure.config import ConfigLoader

logger = getLogger(__name__)


class ScoreCombiner:
    """Handles score combination and adaptive weighting"""

    def __init__(self, config: ConfigLoader):
        """Initialize with configuration

        Args:
            config: Configuration loader
        """
        self.config = config

        # Load weight configurations
        config_dict = config.config
        self.default_title_weight = self._get_weight(config_dict, "title_weight", 0.5)
        self.default_author_weight = self._get_weight(config_dict, "author_weight", 0.3)
        self.default_publisher_weight = self._get_weight(config_dict, "publisher_weight", 0.2)
        self.generic_title_penalty = self._get_weight(config_dict, "generic_title_penalty", 0.8)

        # Load LCCN boost configuration
        # Try to get from matching config object first (Pydantic model)
        if hasattr(self.config, "matching"):
            self.lccn_score_boost = float(self.config.matching.lccn_score_boost)
        else:
            # Fallback to dict access for testing
            matching_config = config_dict.get("matching", {})
            if isinstance(matching_config, dict):
                boost_value = matching_config.get("lccn_score_boost", 35.0)
                if isinstance(boost_value, (int, float)):
                    self.lccn_score_boost = float(boost_value)
                else:
                    self.lccn_score_boost = 35.0
            else:
                self.lccn_score_boost = 35.0

    def _get_weight(self, config_dict: JSONDict, key: str, default: float) -> float:
        """Get weight value from config with default

        Args:
            config_dict: Configuration dictionary
            key: Weight key to look up
            default: Default value if not found

        Returns:
            Weight value as float
        """
        matching = config_dict.get("matching", {})
        if not isinstance(matching, dict):
            return default

        adaptive = matching.get("adaptive_weighting", {})
        if not isinstance(adaptive, dict):
            return default

        weight = adaptive.get(key, default)
        # Pydantic ensures these are valid types, just convert to float
        if isinstance(weight, (int, float)):
            return float(weight)
        return default

    def combine_scores(
        self,
        title_score: float,
        author_score: float,
        publisher_score: float = 0.0,
        has_generic_title: bool = False,
        use_config_weights: bool = True,
        has_lccn_match: bool = False,
        marc_derived: DerivedWorkInfo | None = None,
        copyright_derived: DerivedWorkInfo | None = None,
    ) -> float:
        """Combine individual scores into final similarity score

        Args:
            title_score: Title similarity score (0-100)
            author_score: Author similarity score (0-100)
            publisher_score: Publisher similarity score (0-100)
            has_generic_title: Whether title is generic
            use_config_weights: Whether to use config weights or determine dynamically
            has_lccn_match: Whether this is an LCCN match (applies boost if True)
            marc_derived: Derived work detection info for MARC title
            copyright_derived: Derived work detection info for copyright title

        Returns:
            Combined similarity score (0-100)
        """
        # Phase 3: Missing Field Weight Redistribution
        # Check if exactly ONE field is missing (score == 0) and title matches well
        missing_fields = sum([author_score == 0, publisher_score == 0])

        if missing_fields == 1 and title_score >= 70:
            # Special handling when ONE field is missing but title matches well
            # This avoids unfair penalization when entity appears in different field
            # (e.g., "Commerce Clearing House" as publisher vs author)

            if author_score == 0 and publisher_score > 0:
                # Author missing, redistribute between title and publisher
                logger.debug(
                    f"Missing author field with good title ({title_score:.1f}%), "
                    f"redistributing weights"
                )
                # Weight more heavily on title since it's our anchor
                combined = title_score * 0.6 + publisher_score * 0.4

            elif publisher_score == 0 and author_score > 0:
                # Publisher missing, redistribute between title and author
                logger.debug(
                    f"Missing publisher field with good title ({title_score:.1f}%), "
                    f"redistributing weights"
                )
                # Weight more heavily on title since it's our anchor
                combined = title_score * 0.6 + author_score * 0.4
            else:
                # This shouldn't happen given our conditions, but handle gracefully
                combined = self._calculate_standard_combination(
                    title_score,
                    author_score,
                    publisher_score,
                    has_generic_title,
                    use_config_weights,
                )

        elif missing_fields >= 2 and author_score == 0 and publisher_score == 0:
            # BOTH author AND publisher missing - NO redistribution
            # This is too risky, fall back to standard calculation
            logger.debug("Both author and publisher missing, using standard weights")
            combined = self._calculate_standard_combination(
                title_score, author_score, publisher_score, has_generic_title, use_config_weights
            )
        else:
            # Standard calculation for all other cases
            combined = self._calculate_standard_combination(
                title_score, author_score, publisher_score, has_generic_title, use_config_weights
            )

        # Phase 3B: Multi-Field Validation (REFINED)
        # Prevent single-field matches from creating false positives
        # But be more targeted to avoid hurting legitimate matches

        # Count how many fields have meaningful scores
        sum([title_score > 20, author_score > 20, publisher_score > 20])
        sum([title_score > 70, author_score > 70, publisher_score > 70])

        # Only apply single-field penalty in very specific cases
        # Case 1: ONLY author is high, title is very low (different books by same author)
        if author_score > 80 and title_score < 20 and publisher_score < 20 and not has_lccn_match:
            logger.debug(
                f"Author-only match with very weak other fields (author={author_score:.1f}, title={title_score:.1f}), "
                f"applying 0.3x penalty"
            )
            combined *= 0.3

        # Case 2: ONLY publisher is high, title is very low (different books from same publisher)
        elif publisher_score > 80 and title_score < 20 and author_score < 20 and not has_lccn_match:
            logger.debug(
                f"Publisher-only match with very weak other fields (publisher={publisher_score:.1f}, title={title_score:.1f}), "
                f"applying 0.3x penalty"
            )
            combined *= 0.3

        # Case 3: Title is moderate but NO other support (prone to fuzzy match false positives)
        elif (
            title_score >= 30
            and title_score < 50
            and author_score < 10
            and publisher_score < 10
            and not has_lccn_match
        ):
            # Weak title match with absolutely no other evidence
            logger.debug(
                f"Weak title-only match (title={title_score:.1f}, no other support), "
                f"capping at 25"
            )
            combined = min(combined, 25.0)

        # Phase 5: Derived Work Detection penalty (REFINED)
        # Only apply penalties for high-confidence derived work mismatches
        if marc_derived and copyright_derived:
            # Check if either is detected as a derived work with high confidence
            if (marc_derived.is_derived and marc_derived.confidence >= 0.9) or (
                copyright_derived.is_derived and copyright_derived.confidence >= 0.9
            ):
                # Only penalize when one is derived and the other isn't, or different types
                if marc_derived.is_derived != copyright_derived.is_derived:
                    # One is derived, one isn't - most suspicious
                    penalty_reason = self._get_derived_penalty_reason(
                        marc_derived, copyright_derived
                    )
                    max_confidence = max(marc_derived.confidence, copyright_derived.confidence)
                    penalty_factor = 1.0 - (max_confidence * 0.3)  # Max 30% penalty instead of 50%

                    logger.debug(
                        f"Derived work mismatch: {penalty_reason}, "
                        f"applying {penalty_factor:.2f}x penalty"
                    )
                    combined *= penalty_factor
                elif marc_derived.pattern_matched != copyright_derived.pattern_matched:
                    # Both derived but different types - moderately suspicious
                    penalty_reason = self._get_derived_penalty_reason(
                        marc_derived, copyright_derived
                    )
                    avg_confidence = (marc_derived.confidence + copyright_derived.confidence) / 2
                    penalty_factor = 1.0 - (avg_confidence * 0.15)  # Max 15% penalty instead of 30%

                    logger.debug(
                        f"Different derived work types: {penalty_reason}, "
                        f"applying {penalty_factor:.2f}x penalty"
                    )
                    combined *= penalty_factor
                # If both are the same type of derived work, no penalty (likely legitimate)

        # Apply LCCN boost if this is an LCCN match
        # But use a conditional boost to prevent cataloging errors from passing
        if has_lccn_match and self.lccn_score_boost > 0:
            # Phase 5.5: Smarter LCCN boost to prevent cataloging errors
            # Require meaningful title match OR strong author+publisher match

            if title_score >= 40:
                # Good title match - full boost
                boost = self.lccn_score_boost
                logger.debug(
                    f"Applying full LCCN boost of {boost} (good title match: {title_score:.1f})"
                )
            elif title_score >= 20 and (author_score >= 60 or publisher_score >= 60):
                # Moderate title with strong other field - reduced boost
                boost = self.lccn_score_boost * 0.75
                logger.debug(f"Applying 75% LCCN boost of {boost} (moderate title + strong field)")
            elif author_score >= 80 and publisher_score >= 60:
                # Very strong author AND publisher but weak title - half boost
                # This is suspicious (different book by same author/publisher)
                boost = self.lccn_score_boost * 0.5
                logger.debug(
                    f"Applying 50% LCCN boost of {boost} (strong author+publisher, weak title)"
                )
            else:
                # Poor field agreement - minimal boost
                # LCCN cataloging errors shouldn't pass
                boost = min(5.0, self.lccn_score_boost * 0.25)
                logger.debug(f"Applying minimal LCCN boost of {boost} (poor field agreement)")

            combined = min(100.0, combined + boost)

        return round(combined, 2)

    def _calculate_standard_combination(
        self,
        title_score: float,
        author_score: float,
        publisher_score: float,
        has_generic_title: bool,
        use_config_weights: bool,
    ) -> float:
        """Calculate standard weighted combination of scores

        Args:
            title_score: Title similarity score (0-100)
            author_score: Author similarity score (0-100)
            publisher_score: Publisher similarity score (0-100)
            has_generic_title: Whether title is generic
            use_config_weights: Whether to use config weights or determine dynamically

        Returns:
            Combined similarity score before any boosts
        """
        if use_config_weights:
            # Use weights from configuration
            if has_generic_title:
                scenario = (
                    "generic_with_publisher" if publisher_score > 0 else "generic_no_publisher"
                )
            else:
                scenario = "normal_with_publisher" if publisher_score > 0 else "normal_no_publisher"

            weights = self.config.get_scoring_weights(scenario)

            if weights:
                title_weight = weights.get("title", self.default_title_weight)
                author_weight = weights.get("author", self.default_author_weight)
                publisher_weight = weights.get("publisher", self.default_publisher_weight)
            else:
                # Fallback to defaults
                title_weight = self.default_title_weight
                author_weight = self.default_author_weight
                publisher_weight = self.default_publisher_weight if publisher_score > 0 else 0
        else:
            # Dynamic weight calculation based on scores
            title_weight, author_weight, publisher_weight = self._calculate_dynamic_weights(
                title_score, author_score, publisher_score, has_generic_title
            )

        # Apply generic title penalty if needed
        if has_generic_title:
            title_weight *= self.generic_title_penalty

        # Normalize weights
        total_weight = title_weight + author_weight + publisher_weight
        if total_weight > 0:
            title_weight /= total_weight
            author_weight /= total_weight
            publisher_weight /= total_weight

        # Calculate combined score
        combined = (
            title_score * title_weight
            + author_score * author_weight
            + publisher_score * publisher_weight
        )

        return combined

    def _calculate_dynamic_weights(
        self,
        title_score: float,
        author_score: float,
        publisher_score: float,
        has_generic_title: bool,
    ) -> tuple[float, float, float]:
        """Calculate dynamic weights based on score values

        Args:
            title_score: Title similarity score
            author_score: Author similarity score
            publisher_score: Publisher similarity score
            has_generic_title: Whether title is generic

        Returns:
            Tuple of (title_weight, author_weight, publisher_weight)
        """
        # High confidence in one field can boost its weight
        if title_score >= 90 and not has_generic_title:
            title_weight = 0.6
            author_weight = 0.25
            publisher_weight = 0.15
        elif author_score >= 90:
            title_weight = 0.3 if has_generic_title else 0.4
            author_weight = 0.5
            publisher_weight = 0.2 if publisher_score > 0 else 0.1
        elif publisher_score >= 80:
            title_weight = 0.25 if has_generic_title else 0.35
            author_weight = 0.35
            publisher_weight = 0.3
        else:
            # Default weights
            title_weight = self.default_title_weight
            author_weight = self.default_author_weight
            publisher_weight = self.default_publisher_weight if publisher_score > 0 else 0

        return title_weight, author_weight, publisher_weight

    def _get_derived_penalty_reason(
        self, marc_derived: DerivedWorkInfo, copyright_derived: DerivedWorkInfo
    ) -> str:
        """Get a human-readable reason for derived work penalty

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

    def _calculate_derived_penalty(
        self, marc_derived: DerivedWorkInfo, copyright_derived: DerivedWorkInfo
    ) -> float:
        """Calculate penalty factor for derived works

        Args:
            marc_derived: Derived work info for MARC title
            copyright_derived: Derived work info for copyright title

        Returns:
            Penalty factor to multiply with score (1.0 = no penalty, 0.5 = 50% penalty)
        """
        # If neither is detected as derived, no penalty
        if not marc_derived.is_derived and not copyright_derived.is_derived:
            return 1.0

        # If both are derived works of the same type, less penalty
        if marc_derived.is_derived and copyright_derived.is_derived:
            if marc_derived.pattern_matched == copyright_derived.pattern_matched:
                # Same type of derived work - might be legitimate
                # Apply small penalty based on confidence
                avg_confidence = (marc_derived.confidence + copyright_derived.confidence) / 2
                penalty_factor = 1.0 - (avg_confidence * 0.1)  # Max 10% penalty
                return penalty_factor
            else:
                # Different types of derived works - more suspicious
                # Apply moderate penalty
                avg_confidence = (marc_derived.confidence + copyright_derived.confidence) / 2
                penalty_factor = 1.0 - (avg_confidence * 0.3)  # Max 30% penalty
                return penalty_factor

        # One is derived, one isn't - most suspicious
        # Apply strong penalty based on confidence of the derived work
        if marc_derived.is_derived:
            penalty_factor = 1.0 - (marc_derived.confidence * 0.5)  # Max 50% penalty
        else:
            penalty_factor = 1.0 - (copyright_derived.confidence * 0.5)  # Max 50% penalty

        return penalty_factor
