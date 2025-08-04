# tests/fixtures/matches.py

"""Shared match result fixtures and builders for tests"""

# Third party imports
import pytest

# Local imports
from marc_pd_tool.data.enums import MatchType
from marc_pd_tool.data.publication import MatchResult


class MatchResultBuilder:
    """Builder pattern for creating test match results"""

    @staticmethod
    def registration_match(**kwargs) -> MatchResult:
        """Create a registration match with sensible defaults

        Args:
            **kwargs: Override any default values

        Returns:
            MatchResult instance for registration
        """
        defaults = {
            "source_id": "REG-001",
            "source_type": "registration",
            "matched_title": "Test Book",
            "matched_author": "Author, Test",
            "matched_date": "1950",
            "matched_publisher": "Test Publisher",
            "similarity_score": 95.0,
            "title_score": 98.0,
            "author_score": 92.0,
            "publisher_score": 90.0,
            "year_difference": 0,
            "match_type": MatchType.SIMILARITY,
        }
        defaults.update(kwargs)
        return MatchResult(**defaults)

    @staticmethod
    def renewal_match(**kwargs) -> MatchResult:
        """Create a renewal match with sensible defaults

        Args:
            **kwargs: Override any default values

        Returns:
            MatchResult instance for renewal
        """
        defaults = {
            "source_id": "REN-001",
            "source_type": "renewal",
            "matched_title": "Test Book",
            "matched_author": "Author, Test",
            "matched_date": "1950",
            "matched_publisher": "Test Publisher",
            "similarity_score": 88.0,
            "title_score": 90.0,
            "author_score": 86.0,
            "publisher_score": 85.0,
            "year_difference": 0,
            "match_type": MatchType.SIMILARITY,
        }
        defaults.update(kwargs)
        return MatchResult(**defaults)

    @staticmethod
    def lccn_match(source_type: str = "registration", **kwargs) -> MatchResult:
        """Create an LCCN-based match

        Args:
            source_type: Either "registration" or "renewal"
            **kwargs: Override any default values

        Returns:
            MatchResult instance with LCCN match type
        """
        defaults = {
            "source_id": f"{source_type.upper()}-LCCN-001",
            "source_type": source_type,
            "matched_title": "Test Book",
            "matched_author": "Author, Test",
            "matched_date": "1950",
            "matched_publisher": "Test Publisher",
            "similarity_score": 100.0,
            "title_score": 100.0,
            "author_score": 100.0,
            "publisher_score": 100.0,
            "year_difference": 0,
            "match_type": MatchType.LCCN,
        }
        defaults.update(kwargs)
        return MatchResult(**defaults)

    @staticmethod
    def low_score_match(**kwargs) -> MatchResult:
        """Create a low-scoring match for threshold testing

        Args:
            **kwargs: Override any default values

        Returns:
            MatchResult instance with low scores
        """
        defaults = {
            "source_id": "REG-LOW-001",
            "source_type": "registration",
            "matched_title": "Different Book",
            "matched_author": "Other, Author",
            "matched_date": "1951",
            "matched_publisher": "Other Publisher",
            "similarity_score": 45.0,
            "title_score": 40.0,
            "author_score": 50.0,
            "publisher_score": 45.0,
            "year_difference": 1,
            "match_type": MatchType.SIMILARITY,
        }
        defaults.update(kwargs)
        return MatchResult(**defaults)


@pytest.fixture
def match_builder():
    """Fixture providing the MatchResultBuilder for tests"""
    return MatchResultBuilder


@pytest.fixture
def high_score_registration_match():
    """High-scoring registration match"""
    return MatchResultBuilder.registration_match()


@pytest.fixture
def high_score_renewal_match():
    """High-scoring renewal match"""
    return MatchResultBuilder.renewal_match()


@pytest.fixture
def lccn_registration_match():
    """LCCN-based registration match"""
    return MatchResultBuilder.lccn_match("registration")


@pytest.fixture
def lccn_renewal_match():
    """LCCN-based renewal match"""
    return MatchResultBuilder.lccn_match("renewal")
