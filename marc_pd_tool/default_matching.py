"""Default concrete implementations of matching and scoring interfaces"""

# Standard library imports
from typing import Dict, List, Optional

# Third party imports
from fuzzywuzzy import fuzz

# Local imports
from marc_pd_tool.generic_title_detector import GenericTitleDetector
from marc_pd_tool.matching_api import MatchingEngine, ScoreCombiner, SimilarityCalculator, SimilarityScores
from marc_pd_tool.publication import Publication


class FuzzyWuzzySimilarityCalculator(SimilarityCalculator):
    """Default similarity calculator using fuzzywuzzy library"""

    def calculate_title_similarity(self, marc_title: str, copyright_title: str) -> float:
        """Calculate title similarity using Levenshtein distance"""
        return fuzz.ratio(marc_title, copyright_title)

    def calculate_author_similarity(self, marc_author: str, copyright_author: str) -> float:
        """Calculate author similarity using Levenshtein distance"""
        return fuzz.ratio(marc_author, copyright_author)

    def calculate_publisher_similarity(
        self, 
        marc_publisher: str, 
        copyright_publisher: str, 
        copyright_full_text: str = ""
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
        
        Weighting strategies:
        - Normal titles with publisher: title=60%, author=25%, publisher=15%
        - Generic titles with publisher: title=30%, author=45%, publisher=25%
        - Normal titles without publisher: title=70%, author=30%
        - Generic titles without publisher: title=40%, author=60%
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

        # Apply dynamic scoring weights based on available data
        if marc_pub.publisher and (copyright_pub.publisher or copyright_pub.full_text):
            if has_generic_title:
                # Generic title detected: title=30%, author=45%, publisher=25%
                combined_score = (
                    (title_score * 0.3) + (author_score * 0.45) + (publisher_score * 0.25)
                )
            else:
                # Normal scoring: title=60%, author=25%, publisher=15%
                combined_score = (
                    (title_score * 0.6) + (author_score * 0.25) + (publisher_score * 0.15)
                )
        else:
            # No publisher data available
            if has_generic_title:
                # Generic title, no publisher: title=40%, author=60%
                combined_score = (title_score * 0.4) + (author_score * 0.6)
            else:
                # Normal, no publisher: title=70%, author=30%
                combined_score = (title_score * 0.7) + (author_score * 0.3)

        return combined_score


class DefaultMatchingEngine(MatchingEngine):
    """Default matching engine implementation using current algorithm"""

    def __init__(
        self, 
        similarity_calculator: Optional[SimilarityCalculator] = None,
        score_combiner: Optional[ScoreCombiner] = None
    ):
        """Initialize with optional custom components"""
        self.similarity_calculator = similarity_calculator or FuzzyWuzzySimilarityCalculator()
        self.score_combiner = score_combiner or DynamicWeightingCombiner()

    def find_best_match(
        self,
        marc_pub: Publication,
        copyright_pubs: List[Publication],
        title_threshold: int,
        author_threshold: int,
        year_tolerance: int,
        publisher_threshold: int,
        early_exit_title: int,
        early_exit_author: int,
        generic_detector: Optional[GenericTitleDetector] = None,
    ) -> Optional[Dict]:
        """Find the best matching copyright publication using current algorithm"""
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
                    copyright_pub.full_text if copyright_pub.source == "Renewal" else ""
                )

            # Combine scores using the score combiner
            combined_score = self.score_combiner.combine_scores(
                title_score, author_score, publisher_score,
                marc_pub, copyright_pub, generic_detector
            )

            # Apply thresholds: publisher threshold only matters if MARC has publisher data
            publisher_threshold_met = not marc_pub.publisher or publisher_score >= publisher_threshold

            # Check if this is the best match so far
            # Author threshold check: pass if no author data or if author score meets threshold
            has_author_data = (marc_pub.author and copyright_pub.author) or (marc_pub.main_author and copyright_pub.author)
            author_threshold_met = not has_author_data or author_score >= author_threshold
            
            if (
                combined_score > best_score
                and author_threshold_met
                and publisher_threshold_met
            ):
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