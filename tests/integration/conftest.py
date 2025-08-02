# tests/integration/conftest.py

"""Integration test fixtures and configuration"""

# Standard library imports
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Generator

# Third party imports
import pytest

# Local imports
from marc_pd_tool.loaders.marc_loader import MarcLoader


@pytest.fixture(scope="session")
def test_data_dir() -> Path:
    """Path to test data directory"""
    return Path(__file__).parent.parent / "data"


@pytest.fixture(scope="session")
def sample_marc_file(test_data_dir: Path) -> Path:
    """Path to sample MARC XML file"""
    marc_file = test_data_dir / "sample_marc.xml"
    if not marc_file.exists():
        pytest.skip(f"Sample MARC file not found: {marc_file}")
    return marc_file


@pytest.fixture(scope="session")
def sample_copyright_dir(test_data_dir: Path) -> Path:
    """Path to sample copyright data directory"""
    copyright_dir = test_data_dir / "sample_copyright"
    if not copyright_dir.exists():
        pytest.skip(f"Sample copyright directory not found: {copyright_dir}")
    return copyright_dir


@pytest.fixture(scope="session")
def sample_renewal_dir(test_data_dir: Path) -> Path:
    """Path to sample renewal data directory"""
    renewal_dir = test_data_dir / "sample_renewal"
    if not renewal_dir.exists():
        pytest.skip(f"Sample renewal directory not found: {renewal_dir}")
    return renewal_dir


@pytest.fixture(scope="function")
def temp_output_dir() -> Generator[Path, None, None]:
    """Temporary directory for test outputs"""
    with TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture(scope="function")
def small_marc_file(temp_output_dir: Path) -> Path:
    """Create a small MARC file for testing"""
    marc_content = """<?xml version="1.0" encoding="UTF-8"?>
<collection xmlns="http://www.loc.gov/MARC21/slim">
  <record>
    <leader>01142cam  2200301 a 4500</leader>
    <controlfield tag="001">12345</controlfield>
    <controlfield tag="008">830415s1960    nyu           000 1 eng  </controlfield>
    <datafield tag="010" ind1=" " ind2=" ">
      <subfield code="a">   60007847 </subfield>
    </datafield>
    <datafield tag="100" ind1="1" ind2=" ">
      <subfield code="a">Smith, John Q.</subfield>
    </datafield>
    <datafield tag="245" ind1="1" ind2="0">
      <subfield code="a">A test book :</subfield>
      <subfield code="b">for integration testing /</subfield>
      <subfield code="c">by John Q. Smith.</subfield>
    </datafield>
    <datafield tag="260" ind1=" " ind2=" ">
      <subfield code="a">New York :</subfield>
      <subfield code="b">Test Publisher,</subfield>
      <subfield code="c">1960.</subfield>
    </datafield>
  </record>
  <record>
    <leader>01142cam  2200301 a 4500</leader>
    <controlfield tag="001">67890</controlfield>
    <controlfield tag="008">830415s1955    nyu           000 1 eng  </controlfield>
    <datafield tag="010" ind1=" " ind2=" ">
      <subfield code="a">   55008642 </subfield>
    </datafield>
    <datafield tag="100" ind1="1" ind2=" ">
      <subfield code="a">Jones, Mary.</subfield>
    </datafield>
    <datafield tag="245" ind1="1" ind2="0">
      <subfield code="a">Another test book /</subfield>
      <subfield code="c">Mary Jones.</subfield>
    </datafield>
    <datafield tag="260" ind1=" " ind2=" ">
      <subfield code="a">Boston :</subfield>
      <subfield code="b">Academic Press,</subfield>
      <subfield code="c">1955.</subfield>
    </datafield>
  </record>
</collection>"""
    
    marc_path = temp_output_dir / "small_test.marcxml"
    marc_path.write_text(marc_content)
    return marc_path


@pytest.fixture(scope="function")
def medium_marc_file(temp_output_dir: Path) -> Path:
    """Create a medium-sized MARC file (50 records) for testing"""
    # Generate 50 records with varying years
    records = []
    for i in range(50):
        year = 1940 + i
        record = f"""  <record>
    <leader>01142cam  2200301 a 4500</leader>
    <controlfield tag="001">{1000 + i}</controlfield>
    <controlfield tag="008">830415s{year}    nyu           000 1 eng  </controlfield>
    <datafield tag="010" ind1=" " ind2=" ">
      <subfield code="a">   {year - 1900:02d}{i:06d} </subfield>
    </datafield>
    <datafield tag="100" ind1="1" ind2=" ">
      <subfield code="a">Author{i:03d}, Test.</subfield>
    </datafield>
    <datafield tag="245" ind1="1" ind2="0">
      <subfield code="a">Test Book Number {i} :</subfield>
      <subfield code="b">published in {year} /</subfield>
      <subfield code="c">by Test Author{i:03d}.</subfield>
    </datafield>
    <datafield tag="260" ind1=" " ind2=" ">
      <subfield code="a">New York :</subfield>
      <subfield code="b">Publisher {i % 10},</subfield>
      <subfield code="c">{year}.</subfield>
    </datafield>
  </record>"""
        records.append(record)
    
    marc_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<collection xmlns="http://www.loc.gov/MARC21/slim">
{chr(10).join(records)}
</collection>"""
    
    marc_path = temp_output_dir / "medium_test.marcxml"
    marc_path.write_text(marc_content)
    return marc_path


@pytest.fixture
def mock_copyright_data(temp_output_dir: Path) -> Path:
    """Create mock copyright registration data"""
    copyright_dir = temp_output_dir / "copyright"
    copyright_dir.mkdir()
    
    # Create sample copyright XML files following the expected format
    copyright_content = """<?xml version="1.0" encoding="UTF-8"?>
<copyrightEntries>
    <copyrightEntry id="reg-001">
        <title>A test book for integration testing</title>
        <author>
            <authorName>Smith, John Q.</authorName>
        </author>
        <publisher>
            <pubName>Test Publisher</pubName>
            <pubDate date="1960-01-01">1960</pubDate>
        </publisher>
        <regnum>A123456</regnum>
    </copyrightEntry>
    <copyrightEntry id="reg-002">
        <title>Another test book</title>
        <author>
            <authorName>Jones, Mary</authorName>
        </author>
        <publisher>
            <pubName>Academic Press</pubName>
            <pubDate date="1955-01-01">1955</pubDate>
        </publisher>
        <regnum>A234567</regnum>
    </copyrightEntry>
</copyrightEntries>"""
    
    # Write to a file with year in filename as the loader expects
    (copyright_dir / "1950s_1960s_sample.xml").write_text(copyright_content)
    return copyright_dir


@pytest.fixture
def mock_renewal_data(temp_output_dir: Path) -> Path:
    """Create mock renewal data"""
    renewal_dir = temp_output_dir / "renewal"
    renewal_dir.mkdir()
    
    # Create a sample renewal TSV file
    renewal_content = """title\tauthor\toreg\todat\tid\trdat\tclaimants
A test book for integration testing\tSmith, John Q.\tA123456\t1960\tR123456\t1988\tSmith, John Q.
"""
    
    (renewal_dir / "1988_sample.tsv").write_text(renewal_content)
    return renewal_dir


# Integration test specific settings
@pytest.fixture(scope="session", autouse=True)
def configure_integration_tests():
    """Configure settings for integration tests"""
    # Set longer timeout for integration tests
    import pytest
    pytest.INTEGRATION_TEST_TIMEOUT = 300  # 5 minutes
    
    # Disable cache during integration tests to ensure fresh runs
    import os
    os.environ["MARCPD_DISABLE_CACHE"] = "1"
    
    yield
    
    # Cleanup
    os.environ.pop("MARCPD_DISABLE_CACHE", None)