# marc_pd_tool/application/processing/matching/_lccn_matcher.py

"""LCCN-based matching for copyright records"""

# Standard library imports
from logging import getLogger

# Local imports
from marc_pd_tool.core.domain.publication import Publication

logger = getLogger(__name__)


class LCCNMatcher:
    """Handles LCCN-based matching detection"""

    @staticmethod
    def check_lccn_match(
        marc_pub: Publication, copyright_pubs: list[Publication]
    ) -> tuple[Publication | None, bool]:
        """Check for LCCN match without creating automatic match result

        This method now returns the matching publication and a flag indicating
        whether an LCCN match was found, allowing the scoring pipeline to
        properly evaluate the match with field similarities.

        Args:
            marc_pub: MARC publication to match
            copyright_pubs: List of copyright/renewal publications

        Returns:
            Tuple of (matching_publication, has_lccn_match)
            - matching_publication: The copyright pub with matching LCCN or None
            - has_lccn_match: True if LCCN match found, False otherwise
        """
        if not marc_pub.normalized_lccn:
            return None, False

        for copyright_pub in copyright_pubs:
            if (
                copyright_pub.normalized_lccn
                and marc_pub.normalized_lccn == copyright_pub.normalized_lccn
            ):
                logger.debug(
                    f"LCCN match found: {marc_pub.normalized_lccn} " f"for '{marc_pub.title[:50]}'"
                )
                return copyright_pub, True

        return None, False

    @staticmethod
    def find_lccn_match(
        marc_pub: Publication,
        copyright_pubs: list[Publication],
        source_type: str = "copyright",
        calculate_scores: bool = False,
    ) -> None:
        """Deprecated: Use check_lccn_match instead

        This method is maintained for backward compatibility but should not be used.
        The new check_lccn_match method integrates better with the scoring pipeline.

        Args:
            marc_pub: MARC publication to match
            copyright_pubs: List of copyright/renewal publications
            source_type: Type of source data (unused)
            calculate_scores: Whether to calculate scores (unused)

        Returns:
            Always returns None - LCCN matches are now handled in scoring pipeline
        """
        logger.warning(
            "find_lccn_match is deprecated. LCCN matches are now handled "
            "through the scoring pipeline with configurable boost."
        )
        return None
