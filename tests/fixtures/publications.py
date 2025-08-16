# tests/fixtures/publications.py

"""Shared publication fixtures and builders for tests"""

# Third party imports
import pytest

# Local imports
from marc_pd_tool.core.domain.enums import CopyrightStatus
from marc_pd_tool.core.domain.enums import CountryClassification
from marc_pd_tool.core.domain.enums import MatchType
from marc_pd_tool.core.domain.match_result import MatchResult
from marc_pd_tool.core.domain.publication import Publication


class PublicationBuilder:
    """Builder pattern for creating test publications with sensible defaults"""

    @staticmethod
    def basic_us_publication(**kwargs) -> Publication:
        """Create a basic US publication with sensible defaults

        Args:
            **kwargs: Override any default values

        Returns:
            Publication instance with test data
        """
        defaults = {
            "source_id": "test-001",
            "title": "Test Book",
            "author": "Author, Test",
            "main_author": "Author, Test",
            "pub_date": "1950",
            "publisher": "Test Publisher",
            "place": "New York",
            "edition": "1st ed.",
            "lccn": "",
            "language_code": "eng",
            "country_code": "xxu",
            "country_classification": CountryClassification.US,
        }
        defaults.update(kwargs)

        pub = Publication(**defaults)

        # Set fields that aren't in constructor
        pub.copyright_status = CopyrightStatus.US_NO_MATCH.value
        pub.generic_title_detected = False
        pub.generic_detection_reason = ""
        pub.registration_generic_title = False
        pub.renewal_generic_title = False

        return pub

    @staticmethod
    def with_registration_match(pub: Publication, **match_kwargs) -> Publication:
        """Add a registration match to a publication

        Args:
            pub: Publication to add match to
            **match_kwargs: Override any default match values

        Returns:
            Publication with registration match added
        """
        match_defaults = {
            "source_id": "REG123",
            "source_type": "registration",
            "matched_title": pub.title,
            "matched_author": pub.author,
            "matched_date": pub.pub_date,
            "matched_publisher": pub.publisher,
            "similarity_score": 95.0,
            "title_score": 98.0,
            "author_score": 92.0,
            "publisher_score": 90.0,
            "year_difference": 0,
            "match_type": MatchType.SIMILARITY,
        }
        match_defaults.update(match_kwargs)

        pub.registration_match = MatchResult(**match_defaults)
        return pub

    @staticmethod
    def with_renewal_match(pub: Publication, **match_kwargs) -> Publication:
        """Add a renewal match to a publication

        Args:
            pub: Publication to add match to
            **match_kwargs: Override any default match values

        Returns:
            Publication with renewal match added
        """
        match_defaults = {
            "source_id": "REN456",
            "source_type": "renewal",
            "matched_title": pub.title,
            "matched_author": pub.author,
            "matched_date": pub.pub_date,
            "matched_publisher": pub.publisher,
            "similarity_score": 88.0,
            "title_score": 90.0,
            "author_score": 86.0,
            "publisher_score": 85.0,
            "year_difference": 0,
            "match_type": MatchType.SIMILARITY,
        }
        match_defaults.update(match_kwargs)

        pub.renewal_match = MatchResult(**match_defaults)
        return pub

    @staticmethod
    def batch_publications(count: int = 3, year_start: int = 1950) -> list[Publication]:
        """Create a batch of diverse test publications

        Args:
            count: Number of publications to create
            year_start: Starting year for publications

        Returns:
            List of diverse publications
        """
        publications = []

        for i in range(count):
            year = year_start + i
            pub = PublicationBuilder.basic_us_publication(
                source_id=f"test-{i:03d}",
                title=f"Test Book {i+1}",
                author=f"Author{i+1}, Test",
                main_author=f"Author{i+1}, Test",
                pub_date=str(year),
            )

            # Vary the matches and statuses
            if i % 3 == 0:
                pub = PublicationBuilder.with_registration_match(pub)
                pub.copyright_status = CopyrightStatus.US_REGISTERED_NOT_RENEWED.value
            elif i % 3 == 1:
                pub = PublicationBuilder.with_renewal_match(pub)
                pub.copyright_status = CopyrightStatus.US_RENEWED.value
            else:
                # No matches
                pub.copyright_status = CopyrightStatus.US_NO_MATCH.value

            publications.append(pub)

        return publications


@pytest.fixture
def publication_builder():
    """Fixture providing the PublicationBuilder for tests"""
    return PublicationBuilder


@pytest.fixture
def sample_publications():
    """Standard set of 3 diverse publications for testing

    Returns:
        List containing:
        - Publication with registration match (US_REGISTERED_NOT_RENEWED)
        - Publication with renewal match (US_RENEWED)
        - Publication with no matches (FOREIGN_NO_MATCH_xxk)
    """
    # This replaces the duplicate fixtures across multiple test files
    pubs = []

    # Publication with registration match
    pub1 = PublicationBuilder.basic_us_publication(
        source_id="123",
        title="Test Book One",
        author="Author, Test",
        main_author="Author, Test",
        pub_date="1950",
        publisher="Test Publisher",
        place="New York",
        edition="1st ed.",
        lccn="50012345",
    )
    # Set original fields for testing
    pub1.original_title = "Test Book One"
    pub1.original_author = "Test Author One"
    pub1.original_main_author = "Test Author One"
    pub1.original_publisher = "Test Publisher"
    pub1.original_place = "New York"
    pub1.original_edition = "1st ed."
    pub1.year = 1950
    pub1.normalized_lccn = "50000001"
    pub1 = PublicationBuilder.with_registration_match(pub1, matched_title="Test Book One")
    pub1.copyright_status = CopyrightStatus.US_REGISTERED_NOT_RENEWED.value
    pubs.append(pub1)

    # Publication with renewal match
    pub2 = PublicationBuilder.basic_us_publication(
        source_id="456",
        title="Another Test Book",
        author="Writer, Another",
        main_author="Writer, Another",
        pub_date="1955",
        publisher="Another Publisher",
        place="Chicago",
        edition="",
        lccn="",
    )
    # Set original fields for testing
    pub2.original_title = "Test Book Two"
    pub2.original_author = "Test Author Two"
    pub2.original_main_author = "Test Author Two"
    pub2.original_publisher = "Another Publisher"
    pub2.original_place = "Chicago"
    pub2.original_edition = ""
    pub2.year = 1955
    pub2.normalized_lccn = ""
    pub2 = PublicationBuilder.with_renewal_match(
        pub2, matched_title="Test Book Two", matched_publisher=""
    )
    pub2.copyright_status = CopyrightStatus.US_RENEWED.value
    pubs.append(pub2)

    # Publication with no matches
    pub3 = PublicationBuilder.basic_us_publication(
        source_id="789",
        title="Unknown Book",
        author="Unknown, Author",
        main_author="Unknown, Author",
        pub_date="1960",
        publisher="Unknown Publisher",
        place="London",
        edition="",
        lccn="",
        country_code="xxk",
        country_classification=CountryClassification.NON_US,
    )
    # Set original fields for testing
    pub3.original_title = "Test Book Three"
    pub3.original_author = "Test Author Three"
    pub3.original_main_author = "Test Author Three"
    pub3.original_publisher = "Unknown Publisher"
    pub3.original_place = "London"
    pub3.original_edition = ""
    pub3.year = 1960
    pub3.normalized_lccn = ""
    # Non-US publication should have foreign status
    pub3.copyright_status = f"{CopyrightStatus.FOREIGN_NO_MATCH.value}_xxk"
    pubs.append(pub3)

    return pubs


@pytest.fixture
def us_publication():
    """Single US publication for simple tests"""
    return PublicationBuilder.basic_us_publication()


@pytest.fixture
def non_us_publication():
    """Single non-US publication for simple tests"""
    return PublicationBuilder.basic_us_publication(
        country_code="xxk", country_classification=CountryClassification.NON_US, place="London"
    )
