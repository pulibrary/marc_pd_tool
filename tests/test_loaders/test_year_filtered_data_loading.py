# tests/test_loaders/test_year_filtered_data_loading.py

"""Tests for year-filtered data loading in copyright and renewal loaders"""

# Standard library imports
import os
import tempfile
import unittest

# Local imports
from marc_pd_tool.loaders.copyright_loader import CopyrightDataLoader
from marc_pd_tool.loaders.renewal_loader import RenewalDataLoader


class TestYearFilteredDataLoading(unittest.TestCase):
    """Test year filtering functionality in data loaders"""

    def setUp(self):
        """Set up test fixtures"""
        self.test_dir = tempfile.mkdtemp()

        # Create test copyright XML data with different years
        self.copyright_xml_1950s = """<?xml version="1.0" encoding="UTF-8"?>
<copyrightEntries>
    <copyrightEntry id="reg-001">
        <title>Book from 1955</title>
        <author><authorName>Author One</authorName></author>
        <publisher>
            <pubName>Publisher A</pubName>
            <pubDate date="1955-06-15">1955</pubDate>
        </publisher>
    </copyrightEntry>
    <copyrightEntry id="reg-002">
        <title>Book from 1958</title>
        <author><authorName>Author Two</authorName></author>
        <publisher>
            <pubName>Publisher B</pubName>
            <pubDate date="1958-03-20">1958</pubDate>
        </publisher>
    </copyrightEntry>
</copyrightEntries>"""

        self.copyright_xml_1960s = """<?xml version="1.0" encoding="UTF-8"?>
<copyrightEntries>
    <copyrightEntry id="reg-003">
        <title>Book from 1962</title>
        <author><authorName>Author Three</authorName></author>
        <publisher>
            <pubName>Publisher C</pubName>
            <pubDate date="1962-01-10">1962</pubDate>
        </publisher>
    </copyrightEntry>
    <copyrightEntry id="reg-004">
        <title>Book from 1965</title>
        <author><authorName>Author Four</authorName></author>
        <publisher>
            <pubName>Publisher D</pubName>
            <pubDate date="1965-09-30">1965</pubDate>
        </publisher>
    </copyrightEntry>
</copyrightEntries>"""

        # Create test renewal TSV data with different years
        self.renewal_tsv_1950s = """title	author	oreg	odat	entry_id	rdat	claimants	volume	part	full_text
Book from 1955	Author One	A12345	1955	ren-001	1982	Publisher A			Book from 1955 by Author One
Book from 1958	Author Two	A23456	1958	ren-002	1985	Publisher B			Book from 1958 by Author Two"""

        self.renewal_tsv_1960s = """title	author	oreg	odat	entry_id	rdat	claimants	volume	part	full_text
Book from 1962	Author Three	A34567	1962	ren-003	1989	Publisher C			Book from 1962 by Author Three
Book from 1965	Author Four	A45678	1965	ren-004	1992	Publisher D			Book from 1965 by Author Four"""

        # Create copyright directory and files
        self.copyright_dir = os.path.join(self.test_dir, "copyright")
        os.makedirs(self.copyright_dir)

        with open(os.path.join(self.copyright_dir, "1950s.xml"), "w") as f:
            f.write(self.copyright_xml_1950s)
        with open(os.path.join(self.copyright_dir, "1960s.xml"), "w") as f:
            f.write(self.copyright_xml_1960s)

        # Create renewal directory and files
        self.renewal_dir = os.path.join(self.test_dir, "renewal")
        os.makedirs(self.renewal_dir)

        with open(os.path.join(self.renewal_dir, "1950s.tsv"), "w") as f:
            f.write(self.renewal_tsv_1950s)
        with open(os.path.join(self.renewal_dir, "1960s.tsv"), "w") as f:
            f.write(self.renewal_tsv_1960s)

    def tearDown(self):
        """Clean up test directory"""
        # Standard library imports
        import shutil

        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_copyright_load_all_years(self):
        """Test loading copyright data without year filters"""
        loader = CopyrightDataLoader(self.copyright_dir)
        pubs = loader.load_all_copyright_data()

        self.assertEqual(len(pubs), 4)

        # Check all titles are present
        titles = {pub.title for pub in pubs}
        expected_titles = {"book from 1955", "book from 1958", "book from 1962", "book from 1965"}
        self.assertEqual(titles, expected_titles)

    def test_copyright_load_with_min_year(self):
        """Test loading copyright data with minimum year filter"""
        loader = CopyrightDataLoader(self.copyright_dir)
        pubs = loader.load_all_copyright_data(min_year=1960)

        self.assertEqual(len(pubs), 2)

        # Only 1960s books should be included
        titles = {pub.title for pub in pubs}
        expected_titles = {"book from 1962", "book from 1965"}
        self.assertEqual(titles, expected_titles)

        # Verify all years are >= 1960
        for pub in pubs:
            self.assertIsNotNone(pub.year)
            self.assertGreaterEqual(pub.year, 1960)

    def test_copyright_load_with_max_year(self):
        """Test loading copyright data with maximum year filter"""
        loader = CopyrightDataLoader(self.copyright_dir)
        pubs = loader.load_all_copyright_data(max_year=1959)

        self.assertEqual(len(pubs), 2)

        # Only 1950s books should be included
        titles = {pub.title for pub in pubs}
        expected_titles = {"book from 1955", "book from 1958"}
        self.assertEqual(titles, expected_titles)

        # Verify all years are <= 1959
        for pub in pubs:
            self.assertIsNotNone(pub.year)
            self.assertLessEqual(pub.year, 1959)

    def test_copyright_load_with_year_range(self):
        """Test loading copyright data with both min and max year filters"""
        loader = CopyrightDataLoader(self.copyright_dir)
        pubs = loader.load_all_copyright_data(min_year=1957, max_year=1963)

        self.assertEqual(len(pubs), 2)

        # Only books from 1958 and 1962 should be included
        titles = {pub.title for pub in pubs}
        expected_titles = {"book from 1958", "book from 1962"}
        self.assertEqual(titles, expected_titles)

        # Verify all years are in range
        for pub in pubs:
            self.assertIsNotNone(pub.year)
            self.assertGreaterEqual(pub.year, 1957)
            self.assertLessEqual(pub.year, 1963)

    def test_renewal_load_all_years(self):
        """Test loading renewal data without year filters"""
        loader = RenewalDataLoader(self.renewal_dir)
        pubs = loader.load_all_renewal_data()

        self.assertEqual(len(pubs), 4)

        # Check all titles are present
        titles = {pub.title for pub in pubs}
        expected_titles = {"book from 1955", "book from 1958", "book from 1962", "book from 1965"}
        self.assertEqual(titles, expected_titles)

    def test_renewal_load_with_min_year(self):
        """Test loading renewal data with minimum year filter"""
        loader = RenewalDataLoader(self.renewal_dir)
        pubs = loader.load_all_renewal_data(min_year=1960)

        self.assertEqual(len(pubs), 2)

        # Only 1960s books should be included
        titles = {pub.title for pub in pubs}
        expected_titles = {"book from 1962", "book from 1965"}
        self.assertEqual(titles, expected_titles)

        # Verify all years are >= 1960
        for pub in pubs:
            self.assertIsNotNone(pub.year)
            self.assertGreaterEqual(pub.year, 1960)

    def test_renewal_load_with_max_year(self):
        """Test loading renewal data with maximum year filter"""
        loader = RenewalDataLoader(self.renewal_dir)
        pubs = loader.load_all_renewal_data(max_year=1959)

        self.assertEqual(len(pubs), 2)

        # Only 1950s books should be included
        titles = {pub.title for pub in pubs}
        expected_titles = {"book from 1955", "book from 1958"}
        self.assertEqual(titles, expected_titles)

        # Verify all years are <= 1959
        for pub in pubs:
            self.assertIsNotNone(pub.year)
            self.assertLessEqual(pub.year, 1959)

    def test_renewal_load_with_year_range(self):
        """Test loading renewal data with both min and max year filters"""
        loader = RenewalDataLoader(self.renewal_dir)
        pubs = loader.load_all_renewal_data(min_year=1957, max_year=1963)

        self.assertEqual(len(pubs), 2)

        # Only books from 1958 and 1962 should be included
        titles = {pub.title for pub in pubs}
        expected_titles = {"book from 1958", "book from 1962"}
        self.assertEqual(titles, expected_titles)

        # Verify all years are in range
        for pub in pubs:
            self.assertIsNotNone(pub.year)
            self.assertGreaterEqual(pub.year, 1957)
            self.assertLessEqual(pub.year, 1963)

    def test_no_matches_in_year_range(self):
        """Test loading with year range that matches no records"""
        copyright_loader = CopyrightDataLoader(self.copyright_dir)
        renewal_loader = RenewalDataLoader(self.renewal_dir)

        # Test copyright loader
        copyright_pubs = copyright_loader.load_all_copyright_data(min_year=1970, max_year=1980)
        self.assertEqual(len(copyright_pubs), 0)

        # Test renewal loader
        renewal_pubs = renewal_loader.load_all_renewal_data(min_year=1970, max_year=1980)
        self.assertEqual(len(renewal_pubs), 0)


if __name__ == "__main__":
    unittest.main()
