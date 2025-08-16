# tests/unit/infrastructure/persistence/test_exception_handlers.py

"""Tests for exception handlers in persistence layer"""

# Standard library imports
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock
from unittest.mock import patch

# Local imports
from marc_pd_tool.infrastructure.persistence._copyright_loader import (
    CopyrightDataLoader,
)
from marc_pd_tool.infrastructure.persistence._renewal_loader import RenewalDataLoader


class TestRenewalLoaderExceptionHandlers:
    """Test exception handlers in RenewalDataLoader"""

    def test_extract_publisher_with_attribute_error(self):
        """Test that AttributeError is caught when regex match has no groups"""
        loader = RenewalDataLoader(renewal_dir="dummy")

        # Pass None which will cause AttributeError
        result = loader._extract_publisher_from_full_text(None)
        assert result == ""

    def test_extract_publisher_with_malformed_text(self):
        """Test handling of text that could cause regex issues"""
        loader = RenewalDataLoader(renewal_dir="dummy")

        # Text with unmatched parentheses that could cause issues
        text = "© 1950 (Publisher Name"

        # Should handle gracefully
        result = loader._extract_publisher_from_full_text(text)
        # Should return something or empty string, not crash
        assert isinstance(result, str)

    def test_parse_tsv_with_unicode_decode_error(self):
        """Test that UnicodeDecodeError is caught when TSV has encoding issues"""
        with TemporaryDirectory() as temp_dir:
            # Create a TSV file with bad encoding
            tsv_path = Path(temp_dir) / "bad_encoding.tsv"

            # Write binary data that will cause UnicodeDecodeError
            with open(tsv_path, "wb") as f:
                f.write(b"title\tauthor\tyear\n")
                f.write(b"Test\tAuthor\t\xff\xfe\n")  # Invalid UTF-8 bytes

            loader = RenewalDataLoader(renewal_dir=temp_dir)

            # Should log warning and return empty list, not crash
            result = loader._extract_from_file(tsv_path)
            assert result == []

    def test_extract_from_row_with_key_error(self):
        """Test that KeyError is caught when expected columns are missing"""
        loader = RenewalDataLoader(renewal_dir="dummy")

        # Row missing expected columns
        row = {
            "unexpected_column": "value"
            # Missing: title, author, etc.
        }

        # Should return None, not crash
        result = loader._extract_from_row(row)
        assert result is None

    def test_extract_from_row_with_value_error(self):
        """Test that ValueError is caught when year extraction fails"""
        loader = RenewalDataLoader(renewal_dir="dummy")

        # Row with invalid year format
        row = {
            "title": "Test Book",
            "author": "Test Author",
            "odat": "not-a-date",  # Will cause ValueError in year extraction
            "rdat": "also-not-a-date",
            "id": "123",
            "oreg": "REG123",
        }

        # Should return None or handle gracefully
        result = loader._extract_from_row(row)
        # Either returns None or a Publication with year=None
        assert result is None or result.year is None


class TestCopyrightLoaderExceptionHandlers:
    """Test exception handlers in CopyrightDataLoader"""

    def test_parse_xml_with_parse_error(self):
        """Test that ET.ParseError is caught when XML is malformed"""
        with TemporaryDirectory() as temp_dir:
            # Create malformed XML file
            xml_path = Path(temp_dir) / "malformed.xml"
            with open(xml_path, "w") as f:
                f.write("<root><unclosed_tag></root>")  # Malformed XML

            loader = CopyrightDataLoader(copyright_dir=temp_dir)

            # Should log warning and return empty list
            result = loader._extract_from_file(xml_path)
            assert result == []

    def test_extract_from_entry_with_attribute_error(self):
        """Test that AttributeError is caught when XML elements are missing"""
        loader = CopyrightDataLoader(copyright_dir="dummy")

        # Mock XML element with missing attributes
        mock_element = MagicMock()
        mock_element.find.return_value = None  # Simulates missing elements

        # Should return None, not crash
        result = loader._extract_from_entry(mock_element)
        assert result is None

    def test_extract_from_entry_with_key_error(self):
        """Test that KeyError is caught when expected XML structure is wrong"""
        loader = CopyrightDataLoader(copyright_dir="dummy")

        # Create a mock element that will cause issues
        mock_element = MagicMock()
        # Make find return something that doesn't have .text attribute
        mock_child = MagicMock(spec=[])  # No attributes at all
        mock_element.find.return_value = mock_child

        result = loader._extract_from_entry(mock_element)
        assert result is None

    def test_extract_year_returns_none_for_invalid(self):
        """Test that extract_year returns None for text without valid year"""
        loader = CopyrightDataLoader(copyright_dir="dummy")

        # Create a mock element that will return None from find()
        # This tests the AttributeError path
        mock_element = MagicMock()
        mock_element.find.return_value = None

        # This should handle the None case and return None
        result = loader._extract_year_from_entry(mock_element)
        assert result is None

    @patch("marc_pd_tool.infrastructure.persistence._copyright_loader.extract_year")
    def test_extract_year_with_attribute_error(self, mock_extract_year):
        """Test that AttributeError is caught when element.text is None"""
        loader = CopyrightDataLoader(copyright_dir="dummy")

        # Mock element where find returns None
        mock_element = MagicMock()
        mock_element.find.return_value = None

        result = loader._extract_year_from_entry(mock_element)
        assert result is None

        # extract_year should not have been called
        mock_extract_year.assert_not_called()


class TestCacheManagerExceptionHandlers:
    """Test exception handlers in CacheManager"""

    def test_cache_validation_with_corrupted_metadata(self):
        """Test IndexError/ValueError handling in cache validation"""
        # Local imports
        from marc_pd_tool.infrastructure.cache import CacheManager

        with TemporaryDirectory() as temp_dir:
            manager = CacheManager(cache_dir=temp_dir)

            # Create corrupted metadata
            metadata = {
                "source_files": ["/path/1", "/path/2", "/path/3"],
                "source_mtimes": [123.0],  # Only 1 mtime for 3 files!
            }

            # Mock the file existence check
            with patch("marc_pd_tool.infrastructure.cache._manager.exists", return_value=True):
                with patch(
                    "marc_pd_tool.infrastructure.cache._manager.getmtime", return_value=456.0
                ):
                    # This should trigger IndexError but be caught
                    result = manager._is_cache_valid("test_cache", metadata)

            # Should return False (invalid cache) not crash
            assert result is False

    def test_cache_validation_with_value_error(self):
        """Test ValueError handling when source_files has invalid index"""
        # Local imports
        from marc_pd_tool.infrastructure.cache import CacheManager

        with TemporaryDirectory() as temp_dir:
            manager = CacheManager(cache_dir=temp_dir)

            # Metadata where source path doesn't exist in list
            metadata = {"source_files": ["/path/a", "/path/b"], "source_mtimes": [123.0, 456.0]}

            # Add the non-existent path to metadata to trigger ValueError
            metadata["source_files"] = ["/path/c"]  # This path wasn't tracked

            # Try to validate - should handle gracefully
            with patch("marc_pd_tool.infrastructure.cache._manager.exists", return_value=True):
                result = manager._is_cache_valid("test_cache", metadata)

            # Should return False (invalid cache) not crash
            assert result is False
