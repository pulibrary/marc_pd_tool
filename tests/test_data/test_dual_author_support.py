# tests/test_data/test_dual_author_support.py

"""Test dual author support (245$c and 1xx fields) in Publication class"""

# Local imports
from marc_pd_tool.core.domain.publication import Publication


class TestDualAuthorSupport:
    """Test dual author functionality with both author and main_author fields"""

    def test_publication_with_both_authors(self):
        """Test Publication creation with both author types"""
        pub = Publication(
            title="Test Book",
            author="by John Smith",  # 245$c transcribed
            main_author="Smith, John, 1945-",  # 100$a normalized
            pub_date="1950",
        )

        # Check original values are stored
        assert pub.original_author == "by John Smith"
        assert pub.original_main_author == "Smith, John, 1945-"

        # Check minimal cleanup (whitespace normalization only)
        assert pub.author == "by John Smith"  # Minimal cleanup only
        assert pub.main_author == "Smith, John, 1945-"  # Minimal cleanup only

    def test_publication_with_only_245c_author(self):
        """Test Publication with only 245$c author"""
        pub = Publication(title="Test Book", author="by Jane Doe", main_author="")  # No 1xx field

        assert pub.original_author == "by Jane Doe"
        assert pub.original_main_author is None
        assert pub.author == "by Jane Doe"  # Minimal cleanup only
        assert pub.main_author == ""

    def test_publication_with_only_1xx_author(self):
        """Test Publication with only 1xx author"""
        pub = Publication(title="Test Book", author="", main_author="Doe, Jane")  # No 245$c

        assert pub.original_author is None
        assert pub.original_main_author == "Doe, Jane"
        assert pub.author == ""
        assert pub.main_author == "Doe, Jane"  # Minimal cleanup only

    def test_both_authors_in_to_dict(self):
        """Test that both author fields are included in to_dict output"""
        pub = Publication(
            title="Test Book", author="by Test Author", main_author="Author, Test, 1980-"
        )

        result = pub.to_dict()

        assert "author" in result
        assert "main_author" in result
        assert result["author"] == "by Test Author"
        assert result["main_author"] == "Author, Test, 1980-"

    def test_empty_authors(self):
        """Test handling when both author fields are empty"""
        pub = Publication(title="Test Book", author="", main_author="")

        assert pub.original_author is None
        assert pub.original_main_author is None
        assert pub.author == ""
        assert pub.main_author == ""

    def test_author_normalization(self):
        """Test that both author types are properly normalized"""
        pub = Publication(
            title="Test Book",
            author="By: John Q. Smith, Jr.",
            main_author="Smith, John Q., Jr., 1945-2020",
        )

        # Minimal cleanup (whitespace normalization only)
        assert pub.author == "By: John Q. Smith, Jr."  # Minimal cleanup only
        assert pub.main_author == "Smith, John Q., Jr., 1945-2020"  # Minimal cleanup only

        # Originals should be preserved
        assert pub.original_author == "By: John Q. Smith, Jr."
        assert pub.original_main_author == "Smith, John Q., Jr., 1945-2020"
