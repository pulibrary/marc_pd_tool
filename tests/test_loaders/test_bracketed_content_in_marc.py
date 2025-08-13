# tests/test_loaders/test_bracketed_content_in_marc.py

"""Tests for bracketed content removal in MARC title extraction"""

# Standard library imports
from pathlib import Path
from tempfile import NamedTemporaryFile

# Third party imports
from pytest import fixture

# Local imports
from marc_pd_tool.infrastructure.persistence import MarcLoader


class TestBracketedContentInMarcTitles:
    """Test that bracketed content is removed from MARC titles during extraction"""

    @fixture
    def marc_with_brackets(self):
        """Create MARC XML with titles containing bracketed content"""
        return """<?xml version="1.0" encoding="UTF-8"?>
<collection xmlns="http://www.loc.gov/MARC21/slim">
  <record>
    <controlfield tag="001">test001</controlfield>
    <controlfield tag="008">230101s2023    nyu           000 0 eng d</controlfield>
    <datafield tag="245" ind1="1" ind2="0">
      <subfield code="a">The Great Adventure</subfield>
      <subfield code="b">[microform] :</subfield>
      <subfield code="c">by John Smith.</subfield>
    </datafield>
    <datafield tag="264" ind1=" " ind2="1">
      <subfield code="a">New York :</subfield>
      <subfield code="b">Test Publisher,</subfield>
      <subfield code="c">2023.</subfield>
    </datafield>
  </record>
  <record>
    <controlfield tag="001">test002</controlfield>
    <controlfield tag="008">230101s2023    nyu           000 0 eng d</controlfield>
    <datafield tag="245" ind1="1" ind2="0">
      <subfield code="a">Complete Works [electronic resource]</subfield>
      <subfield code="n">Volume 1</subfield>
      <subfield code="p">Early Writings</subfield>
    </datafield>
    <datafield tag="264" ind1=" " ind2="1">
      <subfield code="a">New York :</subfield>
      <subfield code="b">Digital Press,</subfield>
      <subfield code="c">2023.</subfield>
    </datafield>
  </record>
  <record>
    <controlfield tag="001">test003</controlfield>
    <controlfield tag="008">230101s2023    nyu           000 0 eng d</controlfield>
    <datafield tag="245" ind1="1" ind2="0">
      <subfield code="a">Poetry Collection</subfield>
      <subfield code="b">[sound recording] [1st ed.]</subfield>
    </datafield>
    <datafield tag="264" ind1=" " ind2="1">
      <subfield code="a">New York :</subfield>
      <subfield code="b">Audio Books,</subfield>
      <subfield code="c">2023.</subfield>
    </datafield>
  </record>
</collection>"""

    def test_brackets_removed_from_title_extraction(self, marc_with_brackets):
        """Test that bracketed content is removed during MARC extraction"""
        with NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as f:
            f.write(marc_with_brackets)
            f.flush()

            try:
                loader = MarcLoader(f.name)
                batches = loader.extract_all_batches()
                assert len(batches) == 1
                pubs = batches[0]
                assert len(pubs) == 3

                # First record: brackets in subfield b
                pub1 = pubs[0]
                assert pub1.original_title == "The Great Adventure :"
                assert "[microform]" not in pub1.original_title

                # Second record: brackets in subfield a
                pub2 = pubs[1]
                assert pub2.original_title == "Complete Works Volume 1 Early Writings"
                assert "[electronic resource]" not in pub2.original_title

                # Third record: multiple brackets in subfield b
                pub3 = pubs[2]
                assert pub3.original_title == "Poetry Collection"
                assert "[sound recording]" not in pub3.original_title
                assert "[1st ed.]" not in pub3.original_title

            finally:
                Path(f.name).unlink()

    def test_empty_title_after_bracket_removal(self):
        """Test handling when title becomes empty after bracket removal"""
        marc_xml = """<?xml version="1.0" encoding="UTF-8"?>
<collection xmlns="http://www.loc.gov/MARC21/slim">
  <record>
    <controlfield tag="001">test001</controlfield>
    <controlfield tag="008">230101s2023    nyu           000 0 eng d</controlfield>
    <datafield tag="245" ind1="1" ind2="0">
      <subfield code="a">[microform]</subfield>
    </datafield>
    <datafield tag="264" ind1=" " ind2="1">
      <subfield code="a">New York :</subfield>
      <subfield code="b">Test Publisher,</subfield>
      <subfield code="c">2023.</subfield>
    </datafield>
  </record>
</collection>"""

        with NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as f:
            f.write(marc_xml)
            f.flush()

            try:
                loader = MarcLoader(f.name)
                batches = loader.extract_all_batches()
                # Record should be skipped because title becomes empty
                assert len(batches) == 0
            finally:
                Path(f.name).unlink()

    def test_brackets_in_multiple_subfields(self):
        """Test brackets spread across multiple subfields"""
        marc_xml = """<?xml version="1.0" encoding="UTF-8"?>
<collection xmlns="http://www.loc.gov/MARC21/slim">
  <record>
    <controlfield tag="001">test001</controlfield>
    <controlfield tag="008">230101s2023    nyu           000 0 eng d</controlfield>
    <datafield tag="245" ind1="1" ind2="0">
      <subfield code="a">Main Title [draft]</subfield>
      <subfield code="b">: subtitle [microform]</subfield>
      <subfield code="n">[Part 1]</subfield>
      <subfield code="p">Introduction [revised]</subfield>
    </datafield>
    <datafield tag="264" ind1=" " ind2="1">
      <subfield code="a">New York :</subfield>
      <subfield code="b">Test Publisher,</subfield>
      <subfield code="c">2023.</subfield>
    </datafield>
  </record>
</collection>"""

        with NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as f:
            f.write(marc_xml)
            f.flush()

            try:
                loader = MarcLoader(f.name)
                batches = loader.extract_all_batches()
                assert len(batches) == 1
                pub = batches[0][0]

                # All bracketed content should be removed
                assert pub.original_title == "Main Title : subtitle Introduction"
                assert "[draft]" not in pub.original_title
                assert "[microform]" not in pub.original_title
                assert "[Part 1]" not in pub.original_title
                assert "[revised]" not in pub.original_title

            finally:
                Path(f.name).unlink()

    def test_preserves_non_bracketed_content(self):
        """Test that parentheses and other brackets are preserved"""
        marc_xml = """<?xml version="1.0" encoding="UTF-8"?>
<collection xmlns="http://www.loc.gov/MARC21/slim">
  <record>
    <controlfield tag="001">test001</controlfield>
    <controlfield tag="008">230101s2023    nyu           000 0 eng d</controlfield>
    <datafield tag="245" ind1="1" ind2="0">
      <subfield code="a">Title (with parentheses) [microform]</subfield>
      <subfield code="b">: {with braces}</subfield>
    </datafield>
    <datafield tag="264" ind1=" " ind2="1">
      <subfield code="a">New York :</subfield>
      <subfield code="b">Test Publisher,</subfield>
      <subfield code="c">2023.</subfield>
    </datafield>
  </record>
</collection>"""

        with NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as f:
            f.write(marc_xml)
            f.flush()

            try:
                loader = MarcLoader(f.name)
                batches = loader.extract_all_batches()
                assert len(batches) == 1
                pub = batches[0][0]

                # Only square brackets should be removed
                assert pub.original_title == "Title (with parentheses) : {with braces}"
                assert "(with parentheses)" in pub.original_title
                assert "{with braces}" in pub.original_title
                assert "[microform]" not in pub.original_title

            finally:
                Path(f.name).unlink()
