# marc_pd_tool/application/processing/matching/_lccn_matcher.py

"""LCCN-based matching for copyright records"""

# Standard library imports
from logging import getLogger

# Local imports
from marc_pd_tool.core.domain.publication import Publication
from marc_pd_tool.core.types.results import MatchResultDict

logger = getLogger(__name__)


class LCCNMatcher:
    """Handles LCCN-based exact matching"""

    @staticmethod
    def find_lccn_match(
        marc_pub: Publication,
        copyright_pubs: list[Publication],
        source_type: str = "copyright",
        calculate_scores: bool = False,
    ) -> MatchResultDict | None:
        """Find exact LCCN match

        Args:
            marc_pub: MARC publication to match
            copyright_pubs: List of copyright/renewal publications
            source_type: Type of source data ("copyright" or "renewal")
            calculate_scores: If True, calculate real similarity scores; if False, use -1.0

        Returns:
            MatchResultDict if LCCN match found, None otherwise
        """
        if not marc_pub.normalized_lccn:
            return None

        for copyright_pub in copyright_pubs:
            if (
                copyright_pub.normalized_lccn
                and marc_pub.normalized_lccn == copyright_pub.normalized_lccn
            ):
                logger.debug(
                    f"LCCN match found: {marc_pub.normalized_lccn} " f"for '{marc_pub.title[:50]}'"
                )

                # Use -1.0 for field scores in normal mode to indicate "not checked"
                # or 100.0 in score_everything mode since it's an exact LCCN match
                field_score = 100.0 if calculate_scores else -1.0

                # Return perfect match result for LCCN
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
                        "title": field_score,
                        "author": field_score,
                        "publisher": field_score,
                        "combined": 100.0,  # Always 100 for LCCN match
                    },
                    "is_lccn_match": True,
                    "generic_title_info": None,
                }

        return None
