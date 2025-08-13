# tests/test_loaders/test_renewal_loader_comprehensive.py

"""Comprehensive tests for RenewalDataLoader to improve coverage"""

# Standard library imports
from pathlib import Path

# Local imports
from marc_pd_tool.infrastructure.persistence import RenewalDataLoader


class TestRenewalLoaderEdgeCases:
    """Test edge cases and uncovered paths in RenewalDataLoader"""

    def test_extract_from_file_nonexistent_file(self):
        """Test parsing non-existent TSV file"""
        loader = RenewalDataLoader("/dummy")

        publications = loader._extract_from_file(Path("/nonexistent/file.tsv"))

        assert publications == []

    def test_extract_from_file_empty_file(self, tmp_path):
        """Test parsing empty TSV file"""
        loader = RenewalDataLoader(str(tmp_path))

        # Create empty file
        empty_file = tmp_path / "empty.tsv"
        empty_file.write_text("")

        publications = loader._extract_from_file(empty_file)

        assert publications == []

    def test_extract_from_file_only_header(self, tmp_path):
        """Test parsing TSV with only header row"""
        loader = RenewalDataLoader(str(tmp_path))

        # Create file with only header
        header_file = tmp_path / "header_only.tsv"
        header_file.write_text("title\tauthor\toreg\todat\tid\trdat\tclaimants\n")

        publications = loader._extract_from_file(header_file)

        assert publications == []

    def test_extract_from_file_malformed_rows(self, tmp_path):
        """Test parsing TSV with malformed rows"""
        loader = RenewalDataLoader(str(tmp_path))

        # Create file with inconsistent columns - note entry_id not id
        content = """title\tauthor\toreg\todat\tentry_id\trdat\tclaimants\tfull_text
Complete Row\tAuthor Name\tA123456\t1950-01-01\tR00001\t1977-01-01\tClaimant Name\tComplete full text
Short Row\tAuthor
Extra\tColumns\tHere\tAnd\tMore\tData\tThan\tExpected\tStuff
Normal Row\tNormal Author\tA234567\t1951-01-01\tR00002\t1978-01-01\tAnother Claimant\tNormal full text"""

        tsv_file = tmp_path / "malformed.tsv"
        tsv_file.write_text(content)

        publications = loader._extract_from_file(tsv_file)

        # Should handle malformed rows gracefully
        assert len(publications) >= 2  # At least the complete rows

    def test_extract_from_row_missing_fields(self):
        """Test parsing entry with missing fields"""
        loader = RenewalDataLoader("/dummy")

        # Entry with minimal fields - note entry_id not id
        row = {
            "title": "Minimal Entry",
            "author": "",
            "oreg": "",
            "odat": "",
            "entry_id": "R00001",
            "rdat": "",
            "claimants": "",
            "full_text": "",
        }

        pub = loader._extract_from_row(row)

        assert pub is not None
        assert pub.title == "Minimal Entry"  # Minimal cleanup only
        assert pub.author == ""
        assert pub.source_id == "R00001"
        assert pub.year is None

    def test_extract_from_row_date_formats(self):
        """Test parsing various date formats"""
        loader = RenewalDataLoader("/dummy")

        # Test ISO format (YYYY-MM-DD)
        row1 = {
            "title": "Book 1",
            "author": "Author 1",
            "oreg": "A123456",
            "odat": "1950-12-31",
            "entry_id": "R00001",
            "rdat": "1977-12-31",
            "claimants": "Claimant 1",
            "full_text": "Full text 1",
        }
        pub1 = loader._extract_from_row(row1)
        assert pub1.pub_date == "1950-12-31"
        assert pub1.year == 1950

        # Test YYYYMMDD format
        row2 = {
            "title": "Book 2",
            "author": "Author 2",
            "oreg": "A234567",
            "odat": "19551231",
            "entry_id": "R00002",
            "rdat": "19821231",
            "claimants": "Claimant 2",
            "full_text": "Full text 2",
        }
        pub2 = loader._extract_from_row(row2)
        assert pub2.pub_date == "19551231"
        assert pub2.year is None  # YYYYMMDD format not parsed by year extractor

        # Test YYYY only
        row3 = {
            "title": "Book 3",
            "author": "Author 3",
            "oreg": "A345678",
            "odat": "1960",
            "entry_id": "R00003",
            "rdat": "1987",
            "claimants": "Claimant 3",
            "full_text": "Full text 3",
        }
        pub3 = loader._extract_from_row(row3)
        assert pub3.pub_date == "1960"
        assert pub3.year == 1960

        # Test invalid date
        row4 = {
            "title": "Book 4",
            "author": "Author 4",
            "oreg": "A456789",
            "odat": "invalid-date",
            "entry_id": "R00004",
            "rdat": "also-invalid",
            "claimants": "Claimant 4",
            "full_text": "Full text 4",
        }
        pub4 = loader._extract_from_row(row4)
        assert pub4.pub_date == "invalid-date"
        assert pub4.year is None

    def test_load_all_renewal_data_empty_directory(self, tmp_path):
        """Test loading from empty directory"""
        loader = RenewalDataLoader(str(tmp_path))

        publications = loader.load_all_renewal_data()

        assert publications == []

    def test_load_all_renewal_data_mixed_files(self, tmp_path):
        """Test loading with mixed file types"""
        # Create various files
        (tmp_path / "renewals.tsv").write_text(
            "title\tauthor\toreg\todat\tentry_id\trdat\tclaimants\tfull_text\n"
        )
        (tmp_path / "not_tsv.txt").write_text("This is not a TSV file")
        (tmp_path / "another.csv").write_text("Also not TSV")

        # Create valid TSV
        content = """title\tauthor\toreg\todat\tentry_id\trdat\tclaimants\tfull_text
Test Book\tTest Author\tA123456\t1950-01-01\tR00001\t1977-01-01\tTest Claimant\tTest full text"""
        (tmp_path / "valid.tsv").write_text(content)

        loader = RenewalDataLoader(str(tmp_path))
        publications = loader.load_all_renewal_data()

        # Should only load from TSV files
        assert len(publications) == 1
        assert publications[0].title == "Test Book"  # Minimal cleanup only

    def test_load_all_renewal_data_year_filtered_edge_cases(self, tmp_path):
        """Test year filtering with edge cases"""
        # Use a fresh temp directory to avoid conflicts
        test_dir = tmp_path / "test_year_filter"
        test_dir.mkdir()

        # Create TSV with various years
        content = """title\tauthor\toreg\todat\tentry_id\trdat\tclaimants\tfull_text
Book 1948\tAuthor\tA001\t1948-01-01\tR00001\t1975-01-01\tClaimant\tFull text 1948
Book 1950\tAuthor\tA002\t1950-01-01\tR00002\t1977-01-01\tClaimant\tFull text 1950
Book 1955\tAuthor\tA003\t1955-01-01\tR00003\t1982-01-01\tClaimant\tFull text 1955
Book 1960\tAuthor\tA004\t1960-01-01\tR00004\t1987-01-01\tClaimant\tFull text 1960
Book None\tAuthor\tA005\tinvalid\tR00005\t1990-01-01\tClaimant\tFull text None"""

        tsv_file = test_dir / "renewals.tsv"
        tsv_file.write_text(content)

        loader = RenewalDataLoader(str(test_dir))

        # Test exact year match - includes records with no year
        pubs = loader.load_all_renewal_data(min_year=1950, max_year=1950)
        assert len(pubs) == 2  # 1950 record + no-year record
        # Find the 1950 record
        book_1950 = [p for p in pubs if p.year == 1950][0]
        assert book_1950.title == "Book 1950"  # Minimal cleanup only

        # Test range - includes records with no year
        pubs = loader.load_all_renewal_data(min_year=1950, max_year=1955)
        assert len(pubs) == 3  # 1950, 1955, and no-year records

        # Test with None year record
        pubs = loader.load_all_renewal_data(min_year=1940, max_year=1965)
        assert len(pubs) == 5  # All records including the one with invalid date

        # Test min only
        pubs = loader.load_all_renewal_data(min_year=1955)
        assert len(pubs) == 3  # 1955, 1960, and no-year record

        # Test max only
        pubs = loader.load_all_renewal_data(max_year=1950)
        assert len(pubs) == 3  # 1948, 1950, and no-year record


class TestRenewalLoaderSpecialCases:
    """Test special cases and complex scenarios"""

    def test_unicode_handling(self, tmp_path):
        """Test handling of Unicode characters"""
        loader = RenewalDataLoader(str(tmp_path))

        # Create TSV with Unicode
        content = """title\tauthor\toreg\todat\tid\trdat\tclaimants
La Bibliothèque\tRené Descartes\tA123456\t1950-01-01\tR00001\t1977-01-01\tÉditions Gallimard
Tōkyō Story\t小津 安二郎\tA234567\t1953-01-01\tR00002\t1980-01-01\t松竹株式会社"""

        tsv_file = tmp_path / "unicode.tsv"
        tsv_file.write_text(content, encoding="utf-8")

        publications = loader._extract_from_file(tsv_file)

        assert len(publications) == 2
        assert publications[0].title == "La Bibliothèque"  # Minimal cleanup only
        assert publications[0].author == "René Descartes"  # Minimal cleanup only
        assert publications[1].author == "小津 安二郎"  # Japanese characters preserved

    def test_extract_publisher_from_full_text(self):
        """Test publisher extraction from full_text field"""
        loader = RenewalDataLoader("/dummy")

        # Test typical renewal format
        full_text1 = "TITLE © 1950, A123456. R00001, 15Jan77, Publisher Name (CODE)"
        publisher1 = loader._extract_publisher_from_full_text(full_text1)
        assert publisher1 == "Publisher Name"

        # Test with successor publisher
        full_text2 = "TITLE © 1950, A123456. R00002, 15Jan77, New Publisher, successor to Old Publisher (CODE)"
        publisher2 = loader._extract_publisher_from_full_text(full_text2)
        assert "New Publisher" in publisher2

        # Test empty full_text
        publisher3 = loader._extract_publisher_from_full_text("")
        assert publisher3 == ""

        # Test full_text without renewal pattern
        full_text4 = "Some book title without proper format"
        publisher4 = loader._extract_publisher_from_full_text(full_text4)
        assert publisher4 == ""

    def test_encoding_errors(self, tmp_path):
        """Test handling of encoding errors"""
        loader = RenewalDataLoader(str(tmp_path))

        # Create file with mixed encoding (will cause issues)
        tsv_file = tmp_path / "bad_encoding.tsv"

        # Write header in UTF-8
        with open(tsv_file, "w", encoding="utf-8") as f:
            f.write("title\tauthor\toreg\todat\tid\trdat\tclaimants\n")

        # Append data in different encoding (this would normally cause issues)
        with open(tsv_file, "ab") as f:
            # Write some Latin-1 encoded data
            latin1_text = "Café Book\tAuthor Müller\tA123\t1950\tR001\t1977\tPublisher\n"
            f.write(latin1_text.encode("latin-1"))

        # Should handle encoding gracefully
        publications = loader._extract_from_file(tsv_file)

        # May get decoded incorrectly but shouldn't crash
        assert isinstance(publications, list)

    def test_very_large_file_simulation(self, tmp_path):
        """Test handling of large files"""
        loader = RenewalDataLoader(str(tmp_path))

        # Create a file with many entries
        tsv_file = tmp_path / "large.tsv"

        with open(tsv_file, "w") as f:
            # Write header
            f.write("title\tauthor\toreg\todat\tid\trdat\tclaimants\n")

            # Write many rows
            for i in range(1000):
                f.write(
                    f"Book {i}\tAuthor {i}\tA{i:06d}\t1950-01-01\tR{i:06d}\t1977-01-01\tClaimant {i}\n"
                )

        publications = loader._extract_from_file(tsv_file)

        assert len(publications) == 1000
        assert publications[500].title == "Book 500"  # Minimal cleanup only

    def test_special_characters_in_fields(self, tmp_path):
        """Test handling of special characters in TSV fields"""
        loader = RenewalDataLoader(str(tmp_path))

        # Create TSV with tabs and quotes in content
        content = """title\tauthor\toreg\todat\tentry_id\trdat\tclaimants\tfull_text
"Book with, comma"\t"Author, Name"\tA123456\t1950-01-01\tR00001\t1977-01-01\t"Company, Inc."\tFull text 1
Book with\ttab\tAuthor\tName\tA234567\t1951\tR00002\t1978\tPublisher\tFull text 2
"Quoted ""Book"" Title"\tAuthor\tA345678\t1952\tR00003\t1979\tClaimant\tFull text 3"""

        tsv_file = tmp_path / "special_chars.tsv"
        tsv_file.write_text(content)

        publications = loader._extract_from_file(tsv_file)

        # Should handle special characters
        assert len(publications) >= 1
        assert publications[0].title == "Book with, comma"  # Minimal cleanup only

    def test_get_year_range(self, tmp_path):
        """Test getting year range from renewal data"""
        # Test empty directory first
        loader = RenewalDataLoader(str(tmp_path))
        min_year, max_year = loader.year_range
        assert min_year is None
        assert max_year is None

        # Create TSV with year data
        content = """title\tauthor\toreg\todat\tentry_id\trdat\tclaimants\tfull_text
Book 1945\tAuthor\tA001\t1945-01-01\tR00001\t1972-01-01\tClaimant\tFull text
Book 1965\tAuthor\tA002\t1965-01-01\tR00002\t1992-01-01\tClaimant\tFull text
Book None\tAuthor\tA003\tinvalid\tR00003\t1990-01-01\tClaimant\tFull text"""

        tsv_file = tmp_path / "renewals.tsv"
        tsv_file.write_text(content)

        # Create a new loader after files are created (cached_property caches the result)
        loader2 = RenewalDataLoader(str(tmp_path))
        min_year, max_year = loader2.year_range
        assert min_year == 1945
        assert max_year == 1965

    def test_extract_year_from_row(self):
        """Test year extraction from row"""
        loader = RenewalDataLoader("/dummy")

        # Valid year
        row1 = {"odat": "1950-01-01"}
        year1 = loader._extract_year_from_row(row1)
        assert year1 == 1950

        # No date
        row2 = {"odat": ""}
        year2 = loader._extract_year_from_row(row2)
        assert year2 is None

        # Invalid date
        row3 = {"odat": "not-a-date"}
        year3 = loader._extract_year_from_row(row3)
        assert year3 is None

    def test_extract_from_row_no_title(self):
        """Test extraction when title is missing"""
        loader = RenewalDataLoader("/dummy")

        row = {
            "title": "",
            "author": "Author",
            "oreg": "A123456",
            "odat": "1950",
            "entry_id": "R00001",
            "rdat": "1977",
            "claimants": "Claimant",
            "full_text": "Full text",
        }

        pub = loader._extract_from_row(row)
        assert pub is None  # Should return None for missing title
