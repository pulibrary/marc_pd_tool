# marc_pd_tool/application/processing/matching/_match_builder.py

"""Build match result dictionaries from similarity scores"""

# Standard library imports
from logging import getLogger

# Local imports
from marc_pd_tool.application.processing.text_processing import GenericTitleDetector
from marc_pd_tool.core.domain.publication import Publication
from marc_pd_tool.core.types.json import JSONDict
from marc_pd_tool.core.types.results import MatchResultDict

logger = getLogger(__name__)


class MatchResultBuilder:
    """Builds match result dictionaries from publications and scores"""

    @staticmethod
    def create_match_result(
        marc_pub: Publication,
        copyright_pub: Publication,
        title_score: float,
        author_score: float,
        publisher_score: float,
        combined_score: float,
        generic_detector: GenericTitleDetector | None = None,
        is_lccn_match: bool = False,
    ) -> MatchResultDict:
        """Create a match result dictionary

        Args:
            marc_pub: MARC publication
            copyright_pub: Matched copyright/renewal publication
            title_score: Title similarity score
            author_score: Author similarity score
            publisher_score: Publisher similarity score
            combined_score: Combined similarity score
            generic_detector: Generic title detector for flagging generic titles
            is_lccn_match: Whether this is an LCCN match

        Returns:
            MatchResultDict with all match information
        """
        # Check for generic titles if detector provided
        generic_title_info = None
        if generic_detector:
            generic_title_info = MatchResultBuilder._check_generic_titles(
                marc_pub, copyright_pub, generic_detector
            )

        return {
            "copyright_record": {
                "title": copyright_pub.title,
                "author": copyright_pub.author,
                "publisher": copyright_pub.publisher,
                "pub_date": copyright_pub.pub_date or "",
                "year": copyright_pub.year,
                "source_id": copyright_pub.source_id or "",
                "full_text": copyright_pub.full_text,
            },
            "similarity_scores": {
                "title": title_score,
                "author": author_score,
                "publisher": publisher_score,
                "combined": combined_score,
            },
            "is_lccn_match": is_lccn_match,
            "generic_title_info": generic_title_info,
        }

    @staticmethod
    def _check_generic_titles(
        marc_pub: Publication, copyright_pub: Publication, generic_detector: GenericTitleDetector
    ) -> JSONDict | None:
        """Check if titles are generic

        Args:
            marc_pub: MARC publication
            copyright_pub: Copyright/renewal publication
            generic_detector: Generic title detector

        Returns:
            Generic title information dictionary or None
        """
        marc_is_generic = generic_detector.is_generic(marc_pub.title)
        copyright_is_generic = generic_detector.is_generic(copyright_pub.title)

        if marc_is_generic or copyright_is_generic:
            return {
                "has_generic_title": True,
                "marc_title_is_generic": marc_is_generic,
                "marc_detection_reason": (
                    generic_detector.get_detection_reason(marc_pub.title)
                    if marc_is_generic
                    else None
                ),
                "copyright_title_is_generic": copyright_is_generic,
                "copyright_detection_reason": (
                    generic_detector.get_detection_reason(copyright_pub.title)
                    if copyright_is_generic
                    else None
                ),
            }

        return None
