"""Default concrete implementations of matching and scoring interfaces"""

# Standard library imports
from typing import Dict
from typing import List
from typing import Optional

# Third party imports
from fuzzywuzzy import fuzz

# Local imports
from marc_pd_tool.data.publication import Publication
from marc_pd_tool.infrastructure.config_loader import ConfigLoader
from marc_pd_tool.processing.generic_title_detector import GenericTitleDetector
from marc_pd_tool.processing.matching_api import MatchingEngine
from marc_pd_tool.processing.matching_api import ScoreCombiner
from marc_pd_tool.processing.matching_api import SimilarityCalculator
from marc_pd_tool.processing.matching_api import SimilarityScores


class FuzzyWuzzySimilarityCalculator(SimilarityCalculator):
    """Default similarity calculator using fuzzywuzzy library"""

    def calculate_title_similarity(self, marc_title: str, copyright_title: str) -> float:
        """Calculate title similarity using Levenshtein distance"""
        return fuzz.ratio(marc_title, copyright_title)

    def calculate_author_similarity(self, marc_author: str, copyright_author: str) -> float:
        """Calculate author similarity using Levenshtein distance"""
        return fuzz.ratio(marc_author, copyright_author)

    def calculate_publisher_similarity(
        self, marc_publisher: str, copyright_publisher: str, copyright_full_text: str = ""
    ) -> float:
        """Calculate publisher similarity using appropriate fuzzy matching strategy

        Uses partial_ratio for renewal full_text matching, ratio for direct publisher comparison
        """
        if copyright_full_text:
            # For renewals: fuzzy match MARC publisher against renewal full_text
            return fuzz.partial_ratio(marc_publisher, copyright_full_text)
        elif copyright_publisher:
            # For registrations: direct publisher comparison
            return fuzz.ratio(marc_publisher, copyright_publisher)
        else:
            return 0.0


class DynamicWeightingCombiner(ScoreCombiner):
    """Default score combiner using dynamic weighting based on generic title detection"""

    def __init__(self, config: Optional[ConfigLoader] = None):
        """Initialize with optional configuration

        Args:
            config: Configuration loader, uses default if None
        """
        if config is None:
            # Local imports
            from marc_pd_tool.infrastructure.config_loader import get_config

            config = get_config()
        self.config = config

    def combine_scores(
        self,
        title_score: float,
        author_score: float,
        publisher_score: float,
        marc_pub: Publication,
        copyright_pub: Publication,
        generic_detector: Optional[GenericTitleDetector] = None,
    ) -> float:
        """Combine scores using dynamic weighting based on available data and generic titles

        Uses configurable weights from config.json for different scenarios:
        - Normal titles with publisher
        - Generic titles with publisher
        - Normal titles without publisher
        - Generic titles without publisher
        """
        # Determine if any title is generic
        has_generic_title = False
        if generic_detector:
            marc_title_is_generic = generic_detector.is_generic(
                marc_pub.original_title, marc_pub.language_code
            )
            copyright_title_is_generic = generic_detector.is_generic(
                copyright_pub.original_title, copyright_pub.language_code
            )
            has_generic_title = marc_title_is_generic or copyright_title_is_generic

        # Determine scenario and get weights from configuration
        if marc_pub.publisher and (copyright_pub.publisher or copyright_pub.full_text):
            if has_generic_title:
                weights = self.config.get_scoring_weights("generic_with_publisher")
            else:
                weights = self.config.get_scoring_weights("normal_with_publisher")

            combined_score = (
                (title_score * weights["title"])
                + (author_score * weights["author"])
                + (publisher_score * weights["publisher"])
            )
        else:
            # No publisher data available
            if has_generic_title:
                weights = self.config.get_scoring_weights("generic_no_publisher")
            else:
                weights = self.config.get_scoring_weights("normal_no_publisher")

            combined_score = (title_score * weights["title"]) + (author_score * weights["author"])

        return combined_score


class AdaptiveWeightingCombiner(ScoreCombiner):
    """Improved score combiner that redistributes weights when fields are missing"""

    def __init__(self, config: Optional[ConfigLoader] = None):
        """Initialize with optional configuration

        Args:
            config: Configuration loader, uses default if None
        """
        if config is None:
            # Local imports
            from marc_pd_tool.infrastructure.config_loader import get_config

            config = get_config()
        self.config = config

    def _detect_missing_fields(
        self, marc_pub: Publication, copyright_pub: Publication
    ) -> Dict[str, bool]:
        """Detect which fields are genuinely missing (not just poor matches)

        A field is considered missing if BOTH the MARC record and copyright record
        lack meaningful data for that field.

        Returns:
            Dictionary indicating which fields are missing: {'publisher': True/False}
        """
        missing_fields = {}

        # Publisher is missing if MARC has no publisher OR copyright has neither publisher nor full_text
        marc_has_publisher = bool(marc_pub.publisher and marc_pub.publisher.strip())
        copyright_has_publisher = bool(
            (copyright_pub.publisher and copyright_pub.publisher.strip())
            or (copyright_pub.full_text and copyright_pub.full_text.strip())
        )
        missing_fields["publisher"] = not (marc_has_publisher and copyright_has_publisher)

        return missing_fields

    def _redistribute_weights(
        self, original_weights: Dict[str, float], missing_fields: Dict[str, bool]
    ) -> Dict[str, float]:
        """Redistribute weights proportionally when fields are missing

        Args:
            original_weights: Original weight configuration
            missing_fields: Dictionary indicating which fields are missing

        Returns:
            New weights with missing field weights redistributed
        """
        # Start with original weights
        new_weights = original_weights.copy()

        # Calculate total weight of missing fields
        missing_weight = sum(
            original_weights[field]
            for field in missing_fields
            if missing_fields.get(field, False) and field in original_weights
        )

        if missing_weight == 0:
            return new_weights  # No missing fields

        # Calculate total weight of remaining fields
        remaining_fields = [
            field for field in original_weights if not missing_fields.get(field, False)
        ]
        remaining_weight = sum(original_weights[field] for field in remaining_fields)

        if remaining_weight == 0:
            return new_weights  # Edge case: all fields missing

        # Redistribute missing weight proportionally to remaining fields
        for field in remaining_fields:
            proportion = original_weights[field] / remaining_weight
            redistribution = missing_weight * proportion
            new_weights[field] = original_weights[field] + redistribution

        # Remove weights for missing fields
        for field in missing_fields:
            if missing_fields[field] and field in new_weights:
                new_weights[field] = 0.0

        return new_weights

    def combine_scores(
        self,
        title_score: float,
        author_score: float,
        publisher_score: float,
        marc_pub: Publication,
        copyright_pub: Publication,
        generic_detector: Optional[GenericTitleDetector] = None,
    ) -> float:
        """Combine scores using adaptive weighting that redistributes weights for missing fields"""

        # Determine if any title is generic
        has_generic_title = False
        if generic_detector:
            marc_title_is_generic = generic_detector.is_generic(
                marc_pub.original_title, marc_pub.language_code
            )
            copyright_title_is_generic = generic_detector.is_generic(
                copyright_pub.original_title, copyright_pub.language_code
            )
            has_generic_title = marc_title_is_generic or copyright_title_is_generic

        # Detect which fields are missing
        missing_fields = self._detect_missing_fields(marc_pub, copyright_pub)

        # Determine base scenario and get original weights from configuration
        # If both records completely lack publisher data, use no_publisher weights
        marc_has_publisher = bool(marc_pub.publisher and marc_pub.publisher.strip())
        copyright_has_publisher = bool(
            (copyright_pub.publisher and copyright_pub.publisher.strip())
            or (copyright_pub.full_text and copyright_pub.full_text.strip())
        )

        if not marc_has_publisher and not copyright_has_publisher:
            # Both completely lack publisher data - use no_publisher scenario
            if has_generic_title:
                original_weights = self.config.get_scoring_weights("generic_no_publisher")
            else:
                original_weights = self.config.get_scoring_weights("normal_no_publisher")
        else:
            # At least one has publisher data - start with with_publisher and redistribute
            if has_generic_title:
                original_weights = self.config.get_scoring_weights("generic_with_publisher")
            else:
                original_weights = self.config.get_scoring_weights("normal_with_publisher")

        # Redistribute weights for missing fields
        weights = self._redistribute_weights(original_weights, missing_fields)

        # Calculate combined score using redistributed weights
        combined_score = (
            (title_score * weights.get("title", 0.0))
            + (author_score * weights.get("author", 0.0))
            + (publisher_score * weights.get("publisher", 0.0))
        )

        return combined_score


class DefaultMatchingEngine(MatchingEngine):
    """Default matching engine implementation using current algorithm"""

    def __init__(
        self,
        similarity_calculator: Optional[SimilarityCalculator] = None,
        score_combiner: Optional[ScoreCombiner] = None,
        config: Optional[ConfigLoader] = None,
    ):
        """Initialize with optional custom components and configuration

        Args:
            similarity_calculator: Custom similarity calculator
            score_combiner: Custom score combiner
            config: Configuration loader, uses default if None
        """
        if config is None:
            # Local imports
            from marc_pd_tool.infrastructure.config_loader import get_config

            config = get_config()
        self.config = config

        self.similarity_calculator = similarity_calculator or FuzzyWuzzySimilarityCalculator()
        self.score_combiner = score_combiner or AdaptiveWeightingCombiner(config)

    def find_best_match(
        self,
        marc_pub: Publication,
        copyright_pubs: List[Publication],
        title_threshold: Optional[int] = None,
        author_threshold: Optional[int] = None,
        year_tolerance: Optional[int] = None,
        publisher_threshold: Optional[int] = None,
        early_exit_title: Optional[int] = None,
        early_exit_author: Optional[int] = None,
        generic_detector: Optional[GenericTitleDetector] = None,
    ) -> Optional[Dict]:
        """Find the best matching copyright publication using current algorithm"""
        # Use configuration defaults if parameters not provided
        title_threshold = (
            title_threshold if title_threshold is not None else self.config.get_threshold("title")
        )
        author_threshold = (
            author_threshold
            if author_threshold is not None
            else self.config.get_threshold("author")
        )
        year_tolerance = (
            year_tolerance
            if year_tolerance is not None
            else self.config.get_threshold("year_tolerance")
        )
        publisher_threshold = (
            publisher_threshold
            if publisher_threshold is not None
            else self.config.get_threshold("publisher")
        )
        early_exit_title = (
            early_exit_title
            if early_exit_title is not None
            else self.config.get_threshold("early_exit_title")
        )
        early_exit_author = (
            early_exit_author
            if early_exit_author is not None
            else self.config.get_threshold("early_exit_author")
        )

        best_score = 0
        best_match = None

        for copyright_pub in copyright_pubs:
            # Year filtering
            if marc_pub.year and copyright_pub.year:
                if abs(marc_pub.year - copyright_pub.year) > year_tolerance:
                    continue

            # Calculate title similarity - use full title for better part matching
            title_score = self.similarity_calculator.calculate_title_similarity(
                marc_pub.full_title_normalized, copyright_pub.title
            )

            # Skip if title similarity is too low
            if title_score < title_threshold:
                continue

            # Calculate author scores for both 245$c and 1xx fields, take the maximum
            author_score_245c = 0
            if marc_pub.author and copyright_pub.author:
                author_score_245c = self.similarity_calculator.calculate_author_similarity(
                    marc_pub.author, copyright_pub.author
                )

            author_score_1xx = 0
            if marc_pub.main_author and copyright_pub.author:
                author_score_1xx = self.similarity_calculator.calculate_author_similarity(
                    marc_pub.main_author, copyright_pub.author
                )

            # Use the higher of the two author scores
            author_score = max(author_score_245c, author_score_1xx)

            # Calculate publisher score
            publisher_score = 0
            if marc_pub.publisher:
                publisher_score = self.similarity_calculator.calculate_publisher_similarity(
                    marc_pub.publisher,
                    copyright_pub.publisher,
                    copyright_pub.full_text if copyright_pub.source == "Renewal" else "",
                )

            # Combine scores using the score combiner
            combined_score = self.score_combiner.combine_scores(
                title_score,
                author_score,
                publisher_score,
                marc_pub,
                copyright_pub,
                generic_detector,
            )

            # Apply thresholds: publisher threshold only matters if MARC has publisher data
            publisher_threshold_met = (
                not marc_pub.publisher or publisher_score >= publisher_threshold
            )

            # Check if this is the best match so far
            # Author threshold check: pass if no author data or if author score meets threshold
            has_author_data = (marc_pub.author and copyright_pub.author) or (
                marc_pub.main_author and copyright_pub.author
            )
            author_threshold_met = not has_author_data or author_score >= author_threshold

            if combined_score > best_score and author_threshold_met and publisher_threshold_met:
                best_score = combined_score

                # Determine generic title detection info
                marc_title_is_generic = False
                copyright_title_is_generic = False
                if generic_detector:
                    marc_title_is_generic = generic_detector.is_generic(
                        marc_pub.original_title, marc_pub.language_code
                    )
                    copyright_title_is_generic = generic_detector.is_generic(
                        copyright_pub.original_title, copyright_pub.language_code
                    )

                best_match = {
                    "marc_record": marc_pub.to_dict(),
                    "copyright_record": copyright_pub.to_dict(),
                    "similarity_scores": {
                        "title": title_score,
                        "author": author_score,
                        "publisher": publisher_score,
                        "combined": combined_score,
                    },
                    "generic_title_info": {
                        "marc_title_is_generic": marc_title_is_generic,
                        "copyright_title_is_generic": copyright_title_is_generic,
                        "has_generic_title": marc_title_is_generic or copyright_title_is_generic,
                        "marc_detection_reason": (
                            generic_detector.get_detection_reason(
                                marc_pub.original_title, marc_pub.language_code
                            )
                            if generic_detector
                            else "none"
                        ),
                        "copyright_detection_reason": (
                            generic_detector.get_detection_reason(
                                copyright_pub.original_title, copyright_pub.language_code
                            )
                            if generic_detector
                            else "none"
                        ),
                    },
                }

                # Early termination: Only exit if we have BOTH title and author with very high confidence
                # Consider early exit if we have either author field with high confidence
                has_author_data = (marc_pub.author and copyright_pub.author) or (
                    marc_pub.main_author and copyright_pub.author
                )
                if (
                    title_score >= early_exit_title
                    and has_author_data
                    and author_score >= early_exit_author
                ):
                    break

        return best_match
