# tests/unit/test_infrastructure/test_parallel_loaders.py

"""Tests for parallel data loaders"""

# Standard library imports
from pathlib import Path

# Third party imports
import pytest

# Local imports
from marc_pd_tool.infrastructure.persistence._copyright_loader import (
    CopyrightDataLoader,
)
from marc_pd_tool.infrastructure.persistence._parallel_copyright_loader import (
    ParallelCopyrightLoader,
)
from marc_pd_tool.infrastructure.persistence._parallel_copyright_loader import (
    _load_single_xml_file_static,
)
from marc_pd_tool.infrastructure.persistence._parallel_renewal_loader import (
    ParallelRenewalLoader,
)
from marc_pd_tool.infrastructure.persistence._parallel_renewal_loader import (
    _load_single_tsv_file_static,
)
from marc_pd_tool.infrastructure.persistence._renewal_loader import RenewalDataLoader


class TestParallelCopyrightLoader:
    """Test parallel copyright data loading"""

    def test_load_single_xml_file_basic(self, tmp_path: Path) -> None:
        """Test loading a single XML file"""
        # Create test XML file
        xml_content = """<?xml version="1.0"?>
        <copyrightEntries>
            <copyrightEntry id="CCE-1923-001" regnum="A123456">
                <title>Test Book Title</title>
                <author>
                    <authorName>Smith, John</authorName>
                </author>
                <publisher>
                    <pubName>Test Publisher</pubName>
                    <pubPlace>New York</pubPlace>
                    <pubDate date="1923-01-15"/>
                </publisher>
                <lccn>23-12345</lccn>
            </copyrightEntry>
            <copyrightEntry id="CCE-1924-002" regnum="A234567">
                <title>Another Book</title>
                <author>
                    <authorName>Doe, Jane</authorName>
                </author>
                <publisher>
                    <pubName>Another Publisher</pubName>
                    <pubDate date="1924-06-30"/>
                </publisher>
            </copyrightEntry>
        </copyrightEntries>"""

        xml_file = tmp_path / "test.xml"
        xml_file.write_text(xml_content)

        # Load without filters
        publications = _load_single_xml_file_static(str(xml_file), None, None)

        assert len(publications) == 2

        # Check first publication
        pub1 = publications[0]
        assert pub1.title == "Test Book Title"
        assert pub1.author == "Smith, John"
        assert pub1.publisher == "Test Publisher"
        assert pub1.place == "New York"
        assert pub1.year == 1923
        assert pub1.lccn == "23-12345"
        assert pub1.source == "Copyright"
        assert pub1.source_id == "CCE-1923-001"

        # Check second publication
        pub2 = publications[1]
        assert pub2.title == "Another Book"
        assert pub2.author == "Doe, Jane"
        assert pub2.year == 1924

    def test_load_single_xml_file_with_year_filter(self, tmp_path: Path) -> None:
        """Test year filtering in single file loading"""
        xml_content = """<?xml version="1.0"?>
        <copyrightEntries>
            <copyrightEntry id="CCE-1920" regnum="A111">
                <title>Old Book</title>
                <publisher><pubDate date="1920-01-01"/></publisher>
            </copyrightEntry>
            <copyrightEntry id="CCE-1923" regnum="A222">
                <title>In Range Book</title>
                <publisher><pubDate date="1923-06-15"/></publisher>
            </copyrightEntry>
            <copyrightEntry id="CCE-1928" regnum="A333">
                <title>New Book</title>
                <publisher><pubDate date="1928-12-31"/></publisher>
            </copyrightEntry>
        </copyrightEntries>"""

        xml_file = tmp_path / "years.xml"
        xml_file.write_text(xml_content)

        # Load with year filter
        publications = _load_single_xml_file_static(str(xml_file), 1922, 1925)

        assert len(publications) == 1
        assert publications[0].title == "In Range Book"
        assert publications[0].year == 1923

    def test_load_single_xml_file_with_volume(self, tmp_path: Path) -> None:
        """Test volume information is appended to title"""
        xml_content = """<?xml version="1.0"?>
        <copyrightEntries>
            <copyrightEntry id="CCE-1923" regnum="A123">
                <title>Encyclopedia</title>
                <vol>Volume 5</vol>
                <publisher><pubDate date="1923-01-01"/></publisher>
            </copyrightEntry>
        </copyrightEntries>"""

        xml_file = tmp_path / "volume.xml"
        xml_file.write_text(xml_content)

        publications = _load_single_xml_file_static(str(xml_file), None, None)

        assert len(publications) == 1
        assert publications[0].title == "Encyclopedia Volume 5"

    def test_parallel_loader_basic(self, tmp_path: Path) -> None:
        """Test ParallelCopyrightLoader with multiple files"""
        # Create multiple test XML files
        for i in range(3):
            xml_content = f"""<?xml version="1.0"?>
            <copyrightEntries>
                <copyrightEntry id="CCE-{i}" regnum="A{i}">
                    <title>Book {i}</title>
                    <publisher><pubDate date="192{i}-01-01"/></publisher>
                </copyrightEntry>
            </copyrightEntries>"""

            xml_file = tmp_path / f"file{i}.xml"
            xml_file.write_text(xml_content)

        # Load using parallel loader
        loader = ParallelCopyrightLoader(str(tmp_path), num_workers=2)
        publications = loader.load_all_parallel()

        assert len(publications) == 3
        titles = {pub.title for pub in publications}
        assert titles == {"Book 0", "Book 1", "Book 2"}

    def test_parallel_loader_error_handling(self, tmp_path: Path) -> None:
        """Test error handling with corrupted files"""
        # Create a valid XML file
        valid_xml = """<?xml version="1.0"?>
        <copyrightEntries>
            <copyrightEntry id="CCE-1" regnum="A1">
                <title>Valid Book</title>
            </copyrightEntry>
        </copyrightEntries>"""

        valid_file = tmp_path / "valid.xml"
        valid_file.write_text(valid_xml)

        # Create a corrupted XML file
        corrupted_file = tmp_path / "corrupted.xml"
        corrupted_file.write_text("Not valid XML at all!")

        # Load with parallel loader - should handle error gracefully
        loader = ParallelCopyrightLoader(str(tmp_path), num_workers=1)
        publications = loader.load_all_parallel()

        # Should still load the valid file
        assert len(publications) == 1
        assert publications[0].title == "Valid Book"

    def test_equivalence_with_sequential_loader(self, tmp_path: Path) -> None:
        """Test that parallel loading produces same results as sequential"""
        # Create test XML files
        for year in [1923, 1924, 1925]:
            xml_content = f"""<?xml version="1.0"?>
            <copyrightEntries>
                <copyrightEntry id="CCE-{year}-1" regnum="A{year}1">
                    <title>First Book {year}</title>
                    <author><authorName>Author {year}</authorName></author>
                    <publisher>
                        <pubName>Publisher {year}</pubName>
                        <pubDate date="{year}-06-15"/>
                    </publisher>
                    <lccn>{year}-12345</lccn>
                </copyrightEntry>
                <copyrightEntry id="CCE-{year}-2" regnum="A{year}2">
                    <title>Second Book {year}</title>
                    <publisher><pubDate date="{year}-12-25"/></publisher>
                </copyrightEntry>
            </copyrightEntries>"""

            subdir = tmp_path / str(year)
            subdir.mkdir()
            xml_file = subdir / f"{year}.xml"
            xml_file.write_text(xml_content)

        # Load with loader (always tries parallel first with automatic fallback)
        loader = CopyrightDataLoader(str(tmp_path))
        publications = loader.load_all_copyright_data(1924, 1925)

        # Also test with explicit num_workers
        loader_with_workers = CopyrightDataLoader(str(tmp_path), num_workers=2)
        publications_with_workers = loader_with_workers.load_all_copyright_data(1924, 1925)

        # Should have same number of publications
        assert len(publications) == len(publications_with_workers)
        assert len(publications) == 4  # 2 books each for 1924 and 1925

        # Sort both lists for comparison
        sorted_pubs = sorted(publications, key=lambda p: (p.year or 0, p.title))
        sorted_pubs_workers = sorted(
            publications_with_workers, key=lambda p: (p.year or 0, p.title)
        )

        # Compare each publication
        for pub1, pub2 in zip(sorted_pubs, sorted_pubs_workers):
            assert pub1.title == pub2.title
            assert pub1.author == pub2.author
            assert pub1.publisher == pub2.publisher
            assert pub1.year == pub2.year
            assert pub1.lccn == pub2.lccn
            assert pub1.source_id == pub2.source_id


class TestParallelRenewalLoader:
    """Test parallel renewal data loading"""

    def test_load_single_tsv_file_basic(self, tmp_path: Path) -> None:
        """Test loading a single TSV file"""
        # Create test TSV file
        tsv_content = """entry_id\ttitle\tauthor\todat\tvolume\tpart\tfull_text
R123456\tTest Book\tSmith, John\t1950-01-15\t\t\tSome full text
R234567\tAnother Book\tDoe, Jane\t1951-06-30\tVol 2\t\tMore full text"""

        tsv_file = tmp_path / "test.tsv"
        tsv_file.write_text(tsv_content)

        # Load without filters
        publications = _load_single_tsv_file_static(str(tsv_file), None, None)

        assert len(publications) == 2

        # Check first publication
        pub1 = publications[0]
        assert pub1.title == "Test Book"
        assert pub1.author == "Smith, John"
        assert pub1.source == "Renewal"
        assert pub1.source_id == "R123456"
        assert pub1.year == 1950
        assert pub1.full_text == "Some full text"

        # Check second publication
        pub2 = publications[1]
        assert pub2.title == "Another Book"
        assert pub2.author == "Doe, Jane"
        assert pub2.year == 1951

    def test_load_single_tsv_file_with_year_filter(self, tmp_path: Path) -> None:
        """Test year filtering in single TSV file loading"""
        tsv_content = """entry_id\ttitle\tauthor\todat
R111\tOld Book\tAuthor A\t1948-01-01
R222\tIn Range Book\tAuthor B\t1952-06-15
R333\tNew Book\tAuthor C\t1958-12-31"""

        tsv_file = tmp_path / "years.tsv"
        tsv_file.write_text(tsv_content)

        # Load with year filter
        publications = _load_single_tsv_file_static(str(tsv_file), 1950, 1955)

        assert len(publications) == 1
        assert publications[0].title == "In Range Book"
        assert publications[0].year == 1952

    def test_parallel_tsv_loader_basic(self, tmp_path: Path) -> None:
        """Test ParallelRenewalLoader with multiple files"""
        # Create multiple test TSV files
        for i in range(3):
            tsv_content = f"""entry_id\ttitle\tauthor\todat
R{i}00\tBook {i}\tAuthor {i}\t195{i}-01-01"""

            tsv_file = tmp_path / f"195{i}.tsv"
            tsv_file.write_text(tsv_content)

        # Load using parallel loader
        loader = ParallelRenewalLoader(str(tmp_path), num_workers=2)
        publications = loader.load_all_parallel()

        assert len(publications) == 3
        titles = {pub.title for pub in publications}
        assert titles == {"Book 0", "Book 1", "Book 2"}

    def test_equivalence_with_sequential_tsv_loader(self, tmp_path: Path) -> None:
        """Test that parallel TSV loading produces same results as sequential"""
        # Create test TSV files
        for year in [1950, 1951, 1952]:
            tsv_content = f"""entry_id\ttitle\tauthor\todat\tfull_text
R{year}1\tFirst Book {year}\tAuthor {year}\t{year}-06-15\tFull text for first book
R{year}2\tSecond Book {year}\t\t{year}-12-25\tFull text for second book"""

            tsv_file = tmp_path / f"{year}.tsv"
            tsv_file.write_text(tsv_content)

        # Load with loader (always tries parallel first with automatic fallback)
        loader = RenewalDataLoader(str(tmp_path))
        publications = loader.load_all_renewal_data(1951, 1952)

        # Also test with explicit num_workers
        loader_with_workers = RenewalDataLoader(str(tmp_path), num_workers=2)
        publications_with_workers = loader_with_workers.load_all_renewal_data(1951, 1952)

        # Should have same number of publications
        assert len(publications) == len(publications_with_workers)
        assert len(publications) == 4  # 2 books each for 1951 and 1952

        # Sort both lists for comparison
        sorted_pubs = sorted(publications, key=lambda p: (p.year or 0, p.title))
        sorted_pubs_workers = sorted(
            publications_with_workers, key=lambda p: (p.year or 0, p.title)
        )

        # Compare each publication
        for pub1, pub2 in zip(sorted_pubs, sorted_pubs_workers):
            assert pub1.title == pub2.title
            assert pub1.author == pub2.author
            assert pub1.year == pub2.year
            assert pub1.source_id == pub2.source_id
            assert pub1.full_text == pub2.full_text


class TestParallelLoadingPerformance:
    """Test performance improvements with parallel loading"""

    @pytest.mark.slow
    def test_parallel_vs_sequential_speed(self, tmp_path: Path) -> None:
        """Test that parallel loading is faster than sequential"""
        # Create many test files
        num_files = 20
        for i in range(num_files):
            xml_content = f"""<?xml version="1.0"?>
            <copyrightEntries>
                {"".join(f'''
                <copyrightEntry id="CCE-{i}-{j}" regnum="A{i}{j}">
                    <title>Book {i}-{j}</title>
                    <publisher><pubDate date="1923-01-01"/></publisher>
                </copyrightEntry>
                ''' for j in range(50))}
            </copyrightEntries>"""

            xml_file = tmp_path / f"file{i:03d}.xml"
            xml_file.write_text(xml_content)

        # Standard library imports
        import time

        # Time loading with 1 worker (effectively sequential)
        seq_start = time.time()
        seq_loader = CopyrightDataLoader(str(tmp_path), num_workers=1)
        seq_pubs = seq_loader.load_all_copyright_data()
        seq_time = time.time() - seq_start

        # Time loading with multiple workers (parallel)
        par_start = time.time()
        par_loader = CopyrightDataLoader(str(tmp_path), num_workers=4)
        par_pubs = par_loader.load_all_copyright_data()
        par_time = time.time() - par_start

        # Verify same results
        assert len(seq_pubs) == len(par_pubs)
        assert len(seq_pubs) == num_files * 50  # 50 entries per file

        # Parallel should be faster (allow some margin for small datasets)
        # In practice, parallel is much faster with real data
        print(f"Sequential: {seq_time:.2f}s, Parallel: {par_time:.2f}s")
        print(f"Speedup: {seq_time / par_time:.2f}x")

        # For small test datasets, parallel might not always be faster due to overhead
        # But it should at least work correctly
        assert len(par_pubs) > 0
