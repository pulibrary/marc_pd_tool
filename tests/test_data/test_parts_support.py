"""Test part number and part name support in Publication class"""

# Local imports
from marc_pd_tool.data.publication import Publication


class TestPartSupport:
    """Test part number and part name functionality"""

    def test_publication_with_parts(self):
        """Test Publication creation with part number and part name"""
        pub = Publication(
            title="Complete Works",
            part_number="2",
            part_name="Novels",
            author="Jane Doe",
            pub_date="1950",
        )

        # Check original values are stored
        assert pub.original_title == "Complete Works"
        assert pub.original_part_number == "2"
        assert pub.original_part_name == "Novels"

        # Check normalized values
        assert pub.title == "complete works"
        assert pub.part_number == "2"
        assert pub.part_name == "novels"

    def test_full_title_construction(self):
        """Test full title construction with parts"""
        # Title with both part number and name
        pub1 = Publication(title="Complete Works", part_number="2", part_name="Novels")
        assert pub1.full_title == "Complete Works. Part 2. Novels"

        # Title with only part number
        pub2 = Publication(title="Complete Works", part_number="2")
        assert pub2.full_title == "Complete Works. Part 2"

        # Title with only part name
        pub3 = Publication(title="Complete Works", part_name="Novels")
        assert pub3.full_title == "Complete Works. Novels"

        # Title with no parts
        pub4 = Publication(title="Complete Works")
        assert pub4.full_title == "Complete Works"

    def test_full_title_normalized(self):
        """Test normalized full title construction"""
        pub = Publication(title="Complete Works!", part_number="2nd", part_name="The Novels")
        assert pub.full_title_normalized == "complete works part 2nd the novels"

    def test_parts_in_to_dict(self):
        """Test that part fields are included in to_dict output"""
        pub = Publication(
            title="Complete Works", part_number="2", part_name="Novels", author="Jane Doe"
        )

        result = pub.to_dict()

        assert "part_number" in result
        assert "part_name" in result
        assert "full_title" in result

        assert result["part_number"] == "2"
        assert result["part_name"] == "Novels"
        assert result["full_title"] == "Complete Works. Part 2. Novels"

    def test_empty_parts(self):
        """Test handling of empty part values"""
        pub = Publication(title="Complete Works", part_number="", part_name="")

        assert pub.original_part_number is None
        assert pub.original_part_name is None
        assert pub.part_number == ""
        assert pub.part_name == ""
        assert pub.full_title == "Complete Works"
        assert pub.full_title_normalized == "complete works"

    def test_parts_with_whitespace(self):
        """Test part handling with whitespace"""
        pub = Publication(title="Complete Works", part_number="  2  ", part_name="  The Novels  ")

        # Original values preserve whitespace
        assert pub.original_part_number == "  2  "
        assert pub.original_part_name == "  The Novels  "

        # Normalized values are cleaned
        assert pub.part_number == "2"
        assert pub.part_name == "the novels"

        # Full title uses original values
        assert pub.full_title == "Complete Works. Part   2  .   The Novels  "
