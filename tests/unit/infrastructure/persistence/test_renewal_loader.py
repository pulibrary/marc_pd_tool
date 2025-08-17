# tests/unit/infrastructure/persistence/test_renewal_loader.py

"""Tests for RenewalDataLoader TSV parsing functionality"""

# Standard library imports
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

# Third party imports
from pytest import fixture

# Local imports
from marc_pd_tool.infrastructure.persistence import RenewalDataLoader


@fixture
def sample_renewal_tsv():
    """Sample renewal TSV content for testing"""
    return """title\tauthor\toreg\todat\tid\trdat\tclaimants\tentry_id\tfull_text
The Great Gatsby\tFitzgerald, F. Scott\tA12345\t1925-04-10\tR12345\t1953-05-15\tScribner & Sons\tb3ce7263-9e8b-5f9e-b1a0-190723af8d29\tThe Great Gatsby © 1925, A12345. R12345, 15May53, Scribner & Sons (PWH)
To Kill a Mockingbird\tLee, Harper\tA54321\t1960-07-11\tR54321\t1988-08-20\tLippincott Publishers\tc4df8374-0f9c-6f0f-c2b1-201834bf9e30\tTo Kill a Mockingbird © 1960, A54321. R54321, 20Aug88, Lippincott Publishers (PWH)
Animal Farm\tOrwell, George\tA98765\t1945-03-15\tR98765\t1973-04-20\tSecker & Warburg\td5e09485-1fad-7f1f-d3c2-312945cf0f41\tAnimal Farm © 1945, A98765. R98765, 20Apr73, Secker & Warburg (PWH)"""


@fixture
def malformed_renewal_tsv():
    """Malformed renewal TSV content for testing"""
    return """title\tauthor\toreg\todat\tid\trdat\tclaimants\tentry_id
Incomplete Entry\tTest Author\t\t\t\t\t\t
\t\t\t\t\t\t\t
Missing Fields\t\tA12345\t1950-01-01\t\t\tPublisher Name\tmissing-uuid
Extra\tFields\tA11111\t1940-01-01\tR11111\t1968-01-01\tPublisher\tuuid-test\tExtra\tData\tColumns
Title Only\t
\tAuthor Only\t
"""


@fixture
def empty_renewal_tsv():
    """Empty or header-only TSV content"""
    return """title\tauthor\toreg\todat\tid\trdat\tclaimants\tentry_id"""


@fixture
def no_header_renewal_tsv():
    """TSV content without proper headers"""
    return """The Great Gatsby\tFitzgerald, F. Scott\tA12345\t1925-04-10\tR12345\t1953-05-15\tScribner & Sons\tb3ce7263-9e8b-5f9e-b1a0-190723af8d29"""


@fixture
def temp_renewal_dir(sample_renewal_tsv, malformed_renewal_tsv):
    """Create temporary directory with renewal TSV files"""
    with TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create valid TSV file
        valid_file = temp_path / "valid_renewal.tsv"
        valid_file.write_text(sample_renewal_tsv)

        # Create malformed TSV file
        malformed_file = temp_path / "malformed_renewal.tsv"
        malformed_file.write_text(malformed_renewal_tsv)

        # Create subdirectory (TSV loader doesn't search recursively, but test anyway)
        subdir = temp_path / "subdir"
        subdir.mkdir()
        sub_file = subdir / "sub_renewal.tsv"
        sub_file.write_text(sample_renewal_tsv)

        yield temp_path


class TestRenewalDataLoaderBasic:
    """Test basic RenewalDataLoader functionality"""

    def test_loader_initialization(self):
        """Test basic loader initialization"""
        loader = RenewalDataLoader("/test/path")
        assert str(loader.renewal_dir) == "/test/path"

    def test_loader_initialization_with_path_object(self):
        """Test loader initialization with Path object"""
        path_obj = Path("/test/path")
        loader = RenewalDataLoader(path_obj)
        assert loader.renewal_dir == path_obj


class TestRenewalTSVParsing:
    """Test TSV parsing functionality"""

    def test_parse_valid_renewal_tsv(self, temp_renewal_dir):
        """Test parsing valid renewal TSV files"""
        loader = RenewalDataLoader(temp_renewal_dir)
        publications = loader.load_all_renewal_data()

        # Should have at least 3 publications from valid file
        valid_pubs = [pub for pub in publications if pub.title and len(pub.title) > 5]
        assert len(valid_pubs) >= 3

        # Check first publication (The Great Gatsby)
        gatsby = None
        for pub in publications:
            if "gatsby" in pub.title.lower():
                gatsby = pub
                break

        assert gatsby is not None
        assert "great gatsby" in gatsby.title.lower()
        assert "fitzgerald" in gatsby.author.lower()
        assert gatsby.source == "Renewal"
        assert gatsby.source_id == "b3ce7263-9e8b-5f9e-b1a0-190723af8d29"
        assert "scribner" in gatsby.full_text.lower()

    def test_parse_tsv_with_missing_fields(self, temp_renewal_dir):
        """Test parsing TSV entries with missing fields"""
        loader = RenewalDataLoader(temp_renewal_dir)
        publications = loader.load_all_renewal_data()

        # Should still parse entries with missing fields
        assert len(publications) > 0

        # Should have entries with some missing optional fields, but not empty titles
        # (empty title entries are filtered out by the loader)
        valid_entries = [pub for pub in publications if pub.title and len(pub.title) > 0]
        assert len(valid_entries) > 0

        # Some entries should have missing optional fields like author
        entries_missing_author = [pub for pub in publications if not pub.author or pub.author == ""]
        assert len(entries_missing_author) > 0

    def test_extract_from_file_with_sample_tsv(self, sample_renewal_tsv):
        """Test _extract_from_file method with sample TSV"""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            tsv_file = temp_path / "test.tsv"
            tsv_file.write_text(sample_renewal_tsv)

            loader = RenewalDataLoader(temp_path)
            publications = loader._extract_from_file(tsv_file)

            assert len(publications) == 3

            # Test first publication
            pub1 = publications[0]
            assert "great gatsby" in pub1.title.lower()
            assert "fitzgerald" in pub1.author.lower()
            assert pub1.year == 1925  # Should extract from odat (original date)

            # Test second publication
            pub2 = publications[1]
            assert "mockingbird" in pub2.title.lower()
            assert "lee" in pub2.author.lower()
            assert pub2.year == 1960


class TestRenewalTSVErrorHandling:
    """Test error handling for malformed or invalid TSV"""

    def test_handle_malformed_tsv_file(self, malformed_renewal_tsv):
        """Test handling of malformed TSV files"""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            malformed_file = temp_path / "malformed.tsv"
            malformed_file.write_text(malformed_renewal_tsv)

            loader = RenewalDataLoader(temp_path)

            # Should handle the error gracefully and continue
            publications = loader.load_all_renewal_data()
            assert isinstance(publications, list)
            # Should have some valid entries even with malformed ones
            valid_entries = [pub for pub in publications if pub.title and len(pub.title) > 5]
            assert len(valid_entries) > 0

    def test_handle_nonexistent_directory(self):
        """Test handling of nonexistent directory"""
        loader = RenewalDataLoader("/nonexistent/path")

        # Should handle gracefully by returning empty list when no files found
        publications = loader.load_all_renewal_data()
        assert publications == []

    def test_handle_empty_directory(self):
        """Test handling of directory with no TSV files"""
        with TemporaryDirectory() as temp_dir:
            loader = RenewalDataLoader(temp_dir)
            publications = loader.load_all_renewal_data()

            assert publications == []

    def test_handle_directory_with_non_tsv_files(self):
        """Test handling of directory with non-TSV files"""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create non-TSV files
            text_file = temp_path / "not_tsv.txt"
            text_file.write_text("This is not TSV")

            csv_file = temp_path / "data.csv"
            csv_file.write_text("title,author,year\nTest,Author,1950")

            loader = RenewalDataLoader(temp_path)
            publications = loader.load_all_renewal_data()

            # Should ignore non-TSV files
            assert publications == []

    def test_handle_empty_tsv_file(self, empty_renewal_tsv):
        """Test handling of empty TSV file"""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            empty_file = temp_path / "empty.tsv"
            empty_file.write_text(empty_renewal_tsv)

            loader = RenewalDataLoader(temp_path)
            publications = loader.load_all_renewal_data()

            # Should handle gracefully - just headers, no data
            assert publications == []

    def test_handle_no_header_tsv(self, no_header_renewal_tsv):
        """Test handling of TSV without proper headers"""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            no_header_file = temp_path / "no_header.tsv"
            no_header_file.write_text(no_header_renewal_tsv)

            loader = RenewalDataLoader(temp_path)

            # Should handle gracefully - might fail to parse correctly
            publications = loader.load_all_renewal_data()
            assert isinstance(publications, list)


class TestRenewalTSVFieldExtraction:
    """Test extraction of specific fields from TSV"""

    def test_extract_basic_fields(self, sample_renewal_tsv):
        """Test extraction of title, author from TSV"""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            tsv_file = temp_path / "test.tsv"
            tsv_file.write_text(sample_renewal_tsv)

            loader = RenewalDataLoader(temp_path)
            publications = loader._extract_from_file(tsv_file)

            assert len(publications) == 3

            # Check all publications have required fields
            for pub in publications:
                assert hasattr(pub, "title")
                assert hasattr(pub, "author")
                assert hasattr(pub, "source")
                assert hasattr(pub, "source_id")
                assert pub.source == "Renewal"

    def test_extract_full_text_construction(self, sample_renewal_tsv):
        """Test construction of full_text from TSV fields"""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            tsv_file = temp_path / "test.tsv"
            tsv_file.write_text(sample_renewal_tsv)

            loader = RenewalDataLoader(temp_path)
            publications = loader._extract_from_file(tsv_file)

            assert len(publications) == 3

            # Check that full_text contains relevant information
            pub = publications[0]  # The Great Gatsby entry
            assert pub.full_text  # Should not be empty
            assert "scribner" in pub.full_text.lower()
            assert "sons" in pub.full_text.lower()

    def test_extract_date_information(self, sample_renewal_tsv):
        """Test extraction and parsing of date information"""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            tsv_file = temp_path / "test.tsv"
            tsv_file.write_text(sample_renewal_tsv)

            loader = RenewalDataLoader(temp_path)
            publications = loader._extract_from_file(tsv_file)

            assert len(publications) == 3

            # Check first publication dates
            pub1 = publications[0]
            assert pub1.year == 1925  # Should extract from odat
            assert pub1.pub_date == "1925-04-10"  # Should be odat value

    def test_extract_entry_id_as_source_id(self, sample_renewal_tsv):
        """Test that entry_id becomes source_id"""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            tsv_file = temp_path / "test.tsv"
            tsv_file.write_text(sample_renewal_tsv)

            loader = RenewalDataLoader(temp_path)
            publications = loader._extract_from_file(tsv_file)

            assert len(publications) == 3

            # Check that entry_id is used as source_id
            pub1 = publications[0]
            assert pub1.source_id == "b3ce7263-9e8b-5f9e-b1a0-190723af8d29"

            pub2 = publications[1]
            assert pub2.source_id == "c4df8374-0f9c-6f0f-c2b1-201834bf9e30"


class TestRenewalTSVEncodingAndFormats:
    """Test different encoding and format variations"""

    def test_tsv_with_unicode_characters(self):
        """Test handling of TSV with Unicode characters"""
        unicode_tsv = """title\tauthor\toreg\todat\tid\trdat\tclaimants\tentry_id
Tëst Bøøk\tAuthör, Tëst\tA12345\t1950-01-01\tR12345\t1978-01-01\tPublîsher & Çø.\tuuid-test-123"""

        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            tsv_file = temp_path / "unicode.tsv"
            tsv_file.write_text(unicode_tsv, encoding="utf-8")

            loader = RenewalDataLoader(temp_path)
            publications = loader._extract_from_file(tsv_file)

            assert len(publications) == 1
            pub = publications[0]
            # Unicode characters are preserved (minimal cleanup only)
            assert pub.title == "Tëst Bøøk"
            assert pub.author == "Authör, Tëst"

    def test_tsv_with_quoted_fields(self):
        """Test handling of TSV with quoted fields containing tabs"""
        quoted_tsv = """title\tauthor\toreg\todat\tid\trdat\tclaimants\tentry_id
"Title with\ttabs"\t"Author, with\tcommas"\tA12345\t1950-01-01\tR12345\t1978-01-01\t"Publisher\twith\ttabs"\tuuid-test-123"""

        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            tsv_file = temp_path / "quoted.tsv"
            tsv_file.write_text(quoted_tsv)

            loader = RenewalDataLoader(temp_path)
            publications = loader._extract_from_file(tsv_file)

            assert len(publications) == 1
            pub = publications[0]
            # Note: CSV reader should handle quoted tabs correctly
            assert pub.title  # Should have some title content

    def test_tsv_with_very_long_lines(self):
        """Test handling of TSV with very long field values"""
        long_title = "Very " * 200 + "Long Title"
        long_claimants = "Claimant " * 100 + "List"

        long_line_tsv = f"""title\tauthor\toreg\todat\tid\trdat\tclaimants\tentry_id
{long_title}\tTest Author\tA12345\t1950-01-01\tR12345\t1978-01-01\t{long_claimants}\tuuid-test-123"""

        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            tsv_file = temp_path / "long_lines.tsv"
            tsv_file.write_text(long_line_tsv)

            loader = RenewalDataLoader(temp_path)
            publications = loader._extract_from_file(tsv_file)

            assert len(publications) == 1
            pub = publications[0]
            assert len(pub.original_title) > 1000
            assert "Long Title" in pub.original_title


class TestRenewalDataLoaderPerformance:
    """Test performance-related aspects of renewal data loading"""

    def test_file_discovery_non_recursive(self, temp_renewal_dir):
        """Test that loader finds TSV files in directory (non-recursive)"""
        loader = RenewalDataLoader(temp_renewal_dir)
        publications = loader.load_all_renewal_data()

        # Should find files in root directory only (not subdirectories)
        # Based on the fixture, we have 2 TSV files in root
        assert len(publications) > 0

    def test_file_sorting(self, temp_renewal_dir):
        """Test that files are processed in sorted order"""
        loader = RenewalDataLoader(temp_renewal_dir)

        # Create test files with names that should be sorted
        (temp_renewal_dir / "z_file.tsv").write_text("title\tauthor\nEmpty\tData")
        (temp_renewal_dir / "a_file.tsv").write_text("title\tauthor\nEmpty\tData")
        (temp_renewal_dir / "m_file.tsv").write_text("title\tauthor\nEmpty\tData")

        # Mock _extract_from_file to track file processing order
        processed_files = []

        def track_files(tsv_file):
            processed_files.append(tsv_file.name)
            return []

        # Mock ParallelRenewalLoader to fail immediately so we fall back to sequential
        with patch(
            "marc_pd_tool.infrastructure.persistence._renewal_loader.ParallelRenewalLoader"
        ) as mock_parallel:
            mock_parallel.side_effect = Exception("Force sequential loading")
            with patch.object(loader, "_extract_from_file", side_effect=track_files):
                loader.load_all_renewal_data()

        # Verify files were processed in sorted order
        assert len(processed_files) >= 3
        sorted_test_files = [
            name for name in processed_files if name in ["a_file.tsv", "m_file.tsv", "z_file.tsv"]
        ]
        assert sorted_test_files == sorted(sorted_test_files)

    @patch("marc_pd_tool.infrastructure.persistence._renewal_loader.logger")
    def test_logging_behavior(self, mock_logger, temp_renewal_dir):
        """Test that appropriate logging occurs during loading"""
        loader = RenewalDataLoader(temp_renewal_dir)

        # Mock ParallelRenewalLoader to fail immediately so we fall back to sequential
        with patch(
            "marc_pd_tool.infrastructure.persistence._renewal_loader.ParallelRenewalLoader"
        ) as mock_parallel:
            mock_parallel.side_effect = Exception("Force sequential loading")
            loader.load_all_renewal_data()

        # Verify that info logging was called
        mock_logger.info.assert_called()
        mock_logger.debug.assert_called()


class TestRenewalDataLoaderEdgeCases:
    """Test edge cases and boundary conditions"""

    def test_tsv_with_missing_columns(self):
        """Test handling of TSV with missing expected columns"""
        minimal_tsv = """title\tauthor
Test Book\tTest Author"""

        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            tsv_file = temp_path / "minimal.tsv"
            tsv_file.write_text(minimal_tsv)

            loader = RenewalDataLoader(temp_path)
            publications = loader._extract_from_file(tsv_file)

            # Should handle gracefully, possibly with default values
            assert isinstance(publications, list)

    def test_tsv_with_extra_columns(self):
        """Test handling of TSV with extra unexpected columns"""
        extra_columns_tsv = """title\tauthor\toreg\todat\tid\trdat\tclaimants\tentry_id\textra1\textra2
Test Book\tTest Author\tA12345\t1950-01-01\tR12345\t1978-01-01\tPublisher\tuuid-123\tExtra Data\tMore Data"""

        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            tsv_file = temp_path / "extra.tsv"
            tsv_file.write_text(extra_columns_tsv)

            loader = RenewalDataLoader(temp_path)
            publications = loader._extract_from_file(tsv_file)

            # Should handle gracefully, ignoring extra columns
            assert len(publications) == 1
            pub = publications[0]
            assert pub.title == "Test Book"

    def test_tsv_with_inconsistent_column_counts(self):
        """Test handling of TSV where rows have different column counts"""
        inconsistent_tsv = """title\tauthor\toreg\todat\tid\trdat\tclaimants\tentry_id
Complete Row\tAuthor\tA12345\t1950-01-01\tR12345\t1978-01-01\tPublisher\tuuid-123
Incomplete Row\tAuthor\tA54321
Too Many\tColumns\tA99999\t1960-01-01\tR99999\t1988-01-01\tPublisher\tuuid-456\tExtra\tMore\tColumns"""

        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            tsv_file = temp_path / "inconsistent.tsv"
            tsv_file.write_text(inconsistent_tsv)

            loader = RenewalDataLoader(temp_path)
            publications = loader._extract_from_file(tsv_file)

            # Should handle gracefully - some rows might parse, others might not
            assert isinstance(publications, list)
            # At least the complete row should parse
            complete_entries = [pub for pub in publications if "complete row" in pub.title.lower()]
            assert len(complete_entries) > 0
