"""Test volume/part extraction from renewal TSV data"""

# Local imports
from marc_pd_tool.loaders.renewal_loader import RenewalDataLoader


class TestRenewalVolumeExtraction:
    """Test extraction of volume and part information from renewal TSV"""

    def test_volume_part_extraction(self):
        """Test extraction of volume and part from TSV columns"""
        loader = RenewalDataLoader("dummy_path")

        # Test row with both volume and part
        row1 = {
            "title": "Test Series",
            "author": "Test Author",
            "volume": "4",
            "part": "14A",
            "odat": "1922-12-30",
            "entry_id": "test-id-1",
            "full_text": "Test full text",
        }

        pub1 = loader._extract_from_row(row1)
        assert pub1 is not None
        assert pub1.original_title == "Test Series"
        assert pub1.original_part_number == "4"
        assert pub1.original_part_name == "14A"

    def test_volume_only(self):
        """Test extraction with only volume, no part"""
        loader = RenewalDataLoader("dummy_path")

        row = {
            "title": "Another Series",
            "author": "Another Author",
            "volume": "7",
            "part": "",
            "odat": "1923-01-15",
            "entry_id": "test-id-2",
            "full_text": "Another test",
        }

        pub = loader._extract_from_row(row)
        assert pub is not None
        assert pub.original_part_number == "7"
        assert pub.original_part_name is None

    def test_part_only(self):
        """Test extraction with only part, no volume"""
        loader = RenewalDataLoader("dummy_path")

        row = {
            "title": "Third Series",
            "author": "Third Author",
            "volume": "",
            "part": "B",
            "odat": "1924-02-10",
            "entry_id": "test-id-3",
            "full_text": "Third test",
        }

        pub = loader._extract_from_row(row)
        assert pub is not None
        assert pub.original_part_number is None
        assert pub.original_part_name == "B"

    def test_no_volume_part(self):
        """Test extraction with no volume or part information"""
        loader = RenewalDataLoader("dummy_path")

        row = {
            "title": "Simple Book",
            "author": "Simple Author",
            "volume": "",
            "part": "",
            "odat": "1925-03-20",
            "entry_id": "test-id-4",
            "full_text": "Simple test",
        }

        pub = loader._extract_from_row(row)
        assert pub is not None
        assert pub.original_title == "Simple Book"
        assert pub.original_part_number is None
        assert pub.original_part_name is None

    def test_missing_columns(self):
        """Test graceful handling when volume/part columns are missing"""
        loader = RenewalDataLoader("dummy_path")

        row = {
            "title": "Legacy Book",
            "author": "Legacy Author",
            "odat": "1926-04-15",
            "entry_id": "test-id-5",
            "full_text": "Legacy test",
            # No volume or part columns
        }

        pub = loader._extract_from_row(row)
        assert pub is not None
        assert pub.original_title == "Legacy Book"
        assert pub.original_part_number is None  # Should default to None
        assert pub.original_part_name is None  # Should default to None
