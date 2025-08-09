# tests/test_loaders/test_max_data_year_detection.py

"""Tests for dynamic max data year detection"""

# Standard library imports
from pathlib import Path
from tempfile import TemporaryDirectory

# Local imports
from marc_pd_tool.loaders.copyright_loader import CopyrightDataLoader
from marc_pd_tool.loaders.renewal_loader import RenewalDataLoader


class TestMaxDataYearDetection:
    """Test dynamic detection of maximum data year"""

    def test_copyright_loader_max_year_detection(self):
        """Test that CopyrightDataLoader correctly detects max year from directory names"""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create some year directories
            (temp_path / "1923").mkdir()
            (temp_path / "1950").mkdir()
            (temp_path / "1977").mkdir()
            (temp_path / "1975").mkdir()

            # Create a non-year directory that should be ignored
            (temp_path / "data").mkdir()
            (temp_path / "99999").mkdir()  # Invalid year

            loader = CopyrightDataLoader(temp_dir)
            max_year = loader.get_max_data_year()

            assert max_year == 1977

    def test_copyright_loader_no_year_directories(self):
        """Test CopyrightDataLoader when no year directories exist"""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create only non-year directories
            (temp_path / "data").mkdir()
            (temp_path / "indexes").mkdir()

            loader = CopyrightDataLoader(temp_dir)
            max_year = loader.get_max_data_year()

            assert max_year is None

    def test_copyright_loader_nonexistent_directory(self):
        """Test CopyrightDataLoader with nonexistent directory"""
        loader = CopyrightDataLoader("/nonexistent/path")
        max_year = loader.get_max_data_year()

        assert max_year is None

    def test_renewal_loader_max_year_detection(self):
        """Test that RenewalDataLoader correctly detects max year from filenames"""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create TSV files with year names
            (temp_path / "1950.tsv").touch()
            (temp_path / "1975-from-db.tsv").touch()
            (temp_path / "1991-from-db.tsv").touch()
            (temp_path / "2001-from-db.tsv").touch()

            # Create non-year files that should be ignored
            (temp_path / "metadata.tsv").touch()
            (temp_path / "index.tsv").touch()

            loader = RenewalDataLoader(temp_dir)
            max_year = loader.get_max_data_year()

            assert max_year == 2001

    def test_renewal_loader_no_year_files(self):
        """Test RenewalDataLoader when no year-named files exist"""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create only non-year files
            (temp_path / "data.tsv").touch()
            (temp_path / "index.tsv").touch()

            loader = RenewalDataLoader(temp_dir)
            max_year = loader.get_max_data_year()

            assert max_year is None

    def test_renewal_loader_nonexistent_directory(self):
        """Test RenewalDataLoader with nonexistent directory"""
        loader = RenewalDataLoader("/nonexistent/path")
        max_year = loader.get_max_data_year()

        assert max_year is None

    def test_renewal_loader_mixed_formats(self):
        """Test RenewalDataLoader with various filename formats"""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Various formats that might appear
            (temp_path / "1950.tsv").touch()
            (temp_path / "1975-partial.tsv").touch()
            (temp_path / "1991-from-db.tsv").touch()
            (temp_path / "2001-complete.tsv").touch()
            (temp_path / "bad-1999.tsv").touch()  # Should not match (doesn't start with year)

            loader = RenewalDataLoader(temp_dir)
            max_year = loader.get_max_data_year()

            assert max_year == 2001
