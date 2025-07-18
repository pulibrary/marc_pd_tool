"""MARC XML data extraction for publications"""

# Standard library imports
from logging import getLogger
from pathlib import Path
from typing import List
from typing import Optional
import xml.etree.ElementTree as ET

# Local imports
from marc_pd_tool.enums import AuthorType
from marc_pd_tool.enums import CountryClassification
from marc_pd_tool.publication import Publication
from marc_pd_tool.publication import extract_country_from_marc_008

logger = getLogger(__name__)


class ParallelMarcExtractor:
    def __init__(
        self, marc_path: str, batch_size: int = 1000, min_year: int = None, max_year: int = None
    ):
        self.marc_path = Path(marc_path)
        self.batch_size = batch_size
        self.min_year = min_year
        self.max_year = max_year

    def extract_all_batches(self) -> List[List[Publication]]:
        """Extract all MARC records and return as list of batches"""
        logger.info(f"Extracting all MARC records in batches of {self.batch_size}")

        if not self.marc_path.exists():
            logger.error(f"MARC path not found: {self.marc_path}")
            return []

        # Get list of MARC files to process
        marc_files = self._get_marc_files()
        if not marc_files:
            logger.error(f"No MARC XML files found at: {self.marc_path}")
            return []

        logger.info(f"Found {len(marc_files)} MARC file(s) to process")

        batches = []
        current_batch = []
        total_record_count = 0
        filtered_count = 0

        for marc_file in marc_files:
            logger.info(f"Processing MARC file: {marc_file.name}")
            try:
                context = ET.iterparse(marc_file, events=("start", "end"))
                context = iter(context)
                event, root = next(context)

                file_record_count = 0

                for event, elem in context:
                    if event == "end" and elem.tag.endswith("record"):
                        pub = self._extract_from_record(elem)
                        if pub:
                            if self._should_include_record(pub):
                                current_batch.append(pub)
                            else:
                                filtered_count += 1

                        file_record_count += 1
                        total_record_count += 1

                        if len(current_batch) >= self.batch_size:
                            batches.append(current_batch)
                            logger.debug(
                                f"Created batch {len(batches)} with {len(current_batch)} publications (processed {total_record_count:,} records)"
                            )
                            current_batch = []

                        # Clear element to save memory
                        elem.clear()
                        root.clear()

                logger.info(f"  Processed {file_record_count:,} records from {marc_file.name}")

            except Exception as e:
                logger.error(f"Error parsing MARC file {marc_file}: {e}")
                continue

        # Add final batch
        if current_batch:
            batches.append(current_batch)
            logger.info(
                f"Created final batch {len(batches)} with {len(current_batch)} publications"
            )

        logger.info(
            f"Extracted {len(batches)} batches totaling {sum(len(b) for b in batches):,} publications from {len(marc_files)} file(s)"
        )
        if filtered_count > 0:
            filter_desc = []
            if self.min_year is not None:
                filter_desc.append(f"after {self.min_year}")
            if self.max_year is not None:
                filter_desc.append(f"before {self.max_year} (inclusive)")
            filter_text = " or ".join(filter_desc)
            logger.info(f"Filtered out {filtered_count:,} records ({filter_text})")
        return batches

    def _get_marc_files(self) -> List[Path]:
        """Get list of MARC XML files from path (file or directory)"""
        if self.marc_path.is_file():
            # Single file
            if self.marc_path.suffix.lower() in [".xml", ".marcxml"]:
                return [self.marc_path]
            else:
                logger.warning(f"File {self.marc_path} doesn't have .xml or .marcxml extension")
                return [self.marc_path]  # Try anyway
        elif self.marc_path.is_dir():
            # Directory - find all XML/MARCXML files
            marc_files = []
            for pattern in ["*.xml", "*.marcxml"]:
                marc_files.extend(self.marc_path.glob(pattern))
            return sorted(marc_files)
        else:
            return []

    def _extract_from_record(self, record) -> Optional[Publication]:
        try:
            ns = {"marc": "http://www.loc.gov/MARC21/slim"}

            # Extract title
            title_elem = record.find(".//datafield[@tag='245']/subfield[@code='a']")
            if title_elem is None:
                title_elem = record.find(
                    ".//marc:datafield[@tag='245']/marc:subfield[@code='a']", ns
                )
            title = title_elem.text if title_elem is not None else ""

            if not title:
                return None

            # Extract author with type tracking
            author = ""
            author_type = AuthorType.UNKNOWN

            # Try field 100 (personal names)
            author_elem = record.find(".//datafield[@tag='100']/subfield[@code='a']")
            if author_elem is None:
                author_elem = record.find(
                    ".//marc:datafield[@tag='100']/marc:subfield[@code='a']", ns
                )
            if author_elem is not None:
                author = author_elem.text
                author_type = AuthorType.PERSONAL
            else:
                # Try field 110 (corporate names)
                author_elem = record.find(".//datafield[@tag='110']/subfield[@code='a']")
                if author_elem is None:
                    author_elem = record.find(
                        ".//marc:datafield[@tag='110']/marc:subfield[@code='a']", ns
                    )
                if author_elem is not None:
                    author = author_elem.text
                    author_type = AuthorType.CORPORATE
                else:
                    # Try field 111 (meeting names)
                    author_elem = record.find(".//datafield[@tag='111']/subfield[@code='a']")
                    if author_elem is None:
                        author_elem = record.find(
                            ".//marc:datafield[@tag='111']/marc:subfield[@code='a']", ns
                        )
                    if author_elem is not None:
                        author = author_elem.text
                        author_type = AuthorType.MEETING

            # Default to empty string if no author found
            author = author if author else ""

            # Extract publication date (try 264 first, then 260)
            pub_date_elem = record.find(".//datafield[@tag='264']/subfield[@code='c']")
            if pub_date_elem is None:
                pub_date_elem = record.find(
                    ".//marc:datafield[@tag='264']/marc:subfield[@code='c']", ns
                )
            if pub_date_elem is None:
                pub_date_elem = record.find(".//datafield[@tag='260']/subfield[@code='c']")
            if pub_date_elem is None:
                pub_date_elem = record.find(
                    ".//marc:datafield[@tag='260']/marc:subfield[@code='c']", ns
                )

            # Get 008 field for both publication date and country extraction
            control_008 = record.find(".//controlfield[@tag='008']")
            if control_008 is None:
                control_008 = record.find(".//marc:controlfield[@tag='008']", ns)

            if pub_date_elem is not None:
                pub_date = pub_date_elem.text
            else:
                if control_008 is not None and len(control_008.text) >= 11:
                    pub_date = control_008.text[7:11]
                else:
                    pub_date = ""

            # Extract country information from 008 field
            country_code = ""
            country_classification = CountryClassification.UNKNOWN
            if control_008 is not None and control_008.text:
                country_code, country_classification = extract_country_from_marc_008(
                    control_008.text
                )

            # Extract publisher (try 264 first, then 260)
            publisher_elem = record.find(".//datafield[@tag='264']/subfield[@code='b']")
            if publisher_elem is None:
                publisher_elem = record.find(
                    ".//marc:datafield[@tag='264']/marc:subfield[@code='b']", ns
                )
            if publisher_elem is None:
                publisher_elem = record.find(".//datafield[@tag='260']/subfield[@code='b']")
            if publisher_elem is None:
                publisher_elem = record.find(
                    ".//marc:datafield[@tag='260']/marc:subfield[@code='b']", ns
                )
            publisher = publisher_elem.text if publisher_elem is not None else ""

            # Extract place (try 264 first, then 260)
            place_elem = record.find(".//datafield[@tag='264']/subfield[@code='a']")
            if place_elem is None:
                place_elem = record.find(
                    ".//marc:datafield[@tag='264']/marc:subfield[@code='a']", ns
                )
            if place_elem is None:
                place_elem = record.find(".//datafield[@tag='260']/subfield[@code='a']")
            if place_elem is None:
                place_elem = record.find(
                    ".//marc:datafield[@tag='260']/marc:subfield[@code='a']", ns
                )
            place = place_elem.text if place_elem is not None else ""

            # Extract record ID
            control_001 = record.find(".//controlfield[@tag='001']")
            if control_001 is None:
                control_001 = record.find(".//marc:controlfield[@tag='001']", ns)
            source_id = control_001.text if control_001 is not None else ""

            return Publication(
                title=title,
                author=author,
                pub_date=pub_date,
                publisher=publisher,
                place=place,
                source="MARC",
                source_id=source_id,
                country_code=country_code,
                country_classification=country_classification,
                author_type=author_type,
            )

        except Exception as e:
            return None

    def _should_include_record(self, pub: Publication) -> bool:
        """Check if record should be included based on year filters"""
        if pub.year is None:
            return True  # Include records without years to be safe

        # Check minimum year
        if self.min_year is not None and pub.year < self.min_year:
            return False

        # Check maximum year
        if self.max_year is not None and pub.year > self.max_year:
            return False

        return True
