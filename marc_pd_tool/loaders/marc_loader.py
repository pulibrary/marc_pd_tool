# marc_pd_tool/loaders/marc_loader.py

"""MARC XML data extraction for publications"""

# Standard library imports
from logging import getLogger
from pathlib import Path
import xml.etree.ElementTree as ET

# Local imports
from marc_pd_tool.data.enums import CountryClassification
from marc_pd_tool.data.publication import Publication
from marc_pd_tool.utils.marc_utilities import extract_country_from_marc_008

logger = getLogger(__name__)


class MarcLoader:
    def __init__(
        self,
        marc_path: str,
        batch_size: int = 1000,
        min_year: int | None = None,
        max_year: int | None = None,
        us_only: bool = False,
    ) -> None:
        self.marc_path = Path(marc_path)
        self.batch_size = batch_size
        self.min_year = min_year
        self.max_year = max_year
        self.us_only = us_only

    def extract_all_batches(self) -> list[list[Publication]]:
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
                filter_desc.append(f"before {self.min_year}")
            if self.max_year is not None:
                filter_desc.append(f"after {self.max_year}")
            if self.us_only:
                filter_desc.append("non-US publications")
            filter_text = " or ".join(filter_desc)
            logger.info(f"Filtered out {filtered_count:,} records ({filter_text})")
        return batches

    def _extract_marc_field(
        self, record: ET.Element, ns: dict[str, str], tags: list[str], subfield_code: str
    ) -> ET.Element | None:
        """Extract a MARC field using pattern matching, trying multiple tags in order

        Args:
            record: MARC record element
            ns: Namespace dictionary
            tags: List of tags to try in order (e.g., ['264', '260'])
            subfield_code: Subfield code to extract

        Returns:
            Element if found, None otherwise
        """
        for tag in tags:
            # Try without namespace first
            elem = record.find(f".//datafield[@tag='{tag}']/subfield[@code='{subfield_code}']")
            if elem is not None:
                return elem
            # Try with namespace
            elem = record.find(
                f".//marc:datafield[@tag='{tag}']/marc:subfield[@code='{subfield_code}']", ns
            )
            if elem is not None:
                return elem
        return None

    def _get_marc_files(self) -> list[Path]:
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
            marc_files: list[Path] = []
            for pattern in ["*.xml", "*.marcxml"]:
                marc_files.extend(self.marc_path.glob(pattern))
            return sorted(marc_files)
        else:
            return []

    def _extract_from_record(self, record: ET.Element) -> Publication | None:
        try:
            ns = {"marc": "http://www.loc.gov/MARC21/slim"}

            # Extract complete title from 245 subfields in original order
            title_parts = []

            # Find all subfields under 245 datafield
            title_datafield = record.find(".//datafield[@tag='245']")
            if title_datafield is None:
                title_datafield = record.find(".//marc:datafield[@tag='245']", ns)

            if title_datafield is not None:
                # Get all subfields in their original order
                subfields = title_datafield.findall("./subfield") or title_datafield.findall(
                    "./marc:subfield", ns
                )

                for subfield in subfields:
                    code = subfield.get("code")
                    if code in ["a", "b", "n", "p"] and subfield.text:
                        title_parts.append(subfield.text.strip())

            title = " ".join(title_parts) if title_parts else ""

            # Remove bracketed content from title (e.g., "[microform]", "[electronic resource]")
            if title:
                # Import here to avoid circular import issues
                # Local imports
                from marc_pd_tool.utils.text_utils import remove_bracketed_content

                title = remove_bracketed_content(title)

            if not title:
                return None

            # Extract author from 245$c (statement of responsibility)
            author_elem = record.find(".//datafield[@tag='245']/subfield[@code='c']")
            if author_elem is None:
                author_elem = record.find(
                    ".//marc:datafield[@tag='245']/marc:subfield[@code='c']", ns
                )

            author = author_elem.text if author_elem is not None else ""

            # Extract main author from 1xx fields (100, 110, 111) - priority order
            main_author = ""

            # Try 100$a (personal name) first
            main_author_elem = record.find(".//datafield[@tag='100']/subfield[@code='a']")
            if main_author_elem is None:
                main_author_elem = record.find(
                    ".//marc:datafield[@tag='100']/marc:subfield[@code='a']", ns
                )

            if main_author_elem is not None:
                main_author = main_author_elem.text or ""
                # Clean up dates from personal names (e.g., "Smith, John, 1945-" -> "Smith, John")
                if main_author and "," in main_author:
                    parts = main_author.split(",")
                    if len(parts) >= 3:
                        # Check if the last part looks like a date
                        last_part = parts[-1].strip()
                        if last_part and (last_part[0].isdigit() or last_part.endswith("-")):
                            main_author = ",".join(parts[:-1]).strip()

            # If no 100, try 110$a (corporate name)
            if not main_author:
                main_author_elem = record.find(".//datafield[@tag='110']/subfield[@code='a']")
                if main_author_elem is None:
                    main_author_elem = record.find(
                        ".//marc:datafield[@tag='110']/marc:subfield[@code='a']", ns
                    )
                if main_author_elem is not None:
                    main_author = main_author_elem.text or ""

            # If no 100 or 110, try 111$a (meeting name)
            if not main_author:
                main_author_elem = record.find(".//datafield[@tag='111']/subfield[@code='a']")
                if main_author_elem is None:
                    main_author_elem = record.find(
                        ".//marc:datafield[@tag='111']/marc:subfield[@code='a']", ns
                    )
                if main_author_elem is not None:
                    main_author = main_author_elem.text or ""

            # Ensure main_author is a string
            main_author = main_author if main_author else ""

            # Extract publication date (try 264 first, then 260)
            pub_date_elem = self._extract_marc_field(record, ns, ["264", "260"], "c")

            # Get 008 field for both publication date and country extraction
            control_008 = record.find(".//controlfield[@tag='008']")
            if control_008 is None:
                control_008 = record.find(".//marc:controlfield[@tag='008']", ns)

            if pub_date_elem is not None:
                pub_date = pub_date_elem.text
            else:
                if control_008 is not None and control_008.text and len(control_008.text) >= 11:
                    pub_date = control_008.text[7:11]
                else:
                    pub_date = ""

            # Extract country information from 008 field
            country_code = ""
            country_classification = CountryClassification.UNKNOWN
            language_code = ""
            if control_008 is not None and control_008.text:
                country_code, country_classification = extract_country_from_marc_008(
                    control_008.text
                )
                # Extract language code from positions 35-37
                if len(control_008.text) >= 38:
                    language_code = control_008.text[35:38].strip().lower()

            # Fallback to field 041$a if no language in 008
            if not language_code:
                lang_041_elem = record.find(".//datafield[@tag='041']/subfield[@code='a']")
                if lang_041_elem is None:
                    lang_041_elem = record.find(
                        ".//marc:datafield[@tag='041']/marc:subfield[@code='a']", ns
                    )
                if lang_041_elem is not None and lang_041_elem.text:
                    language_code = lang_041_elem.text.strip().lower()[:3]  # Take first 3 chars

            # Extract publisher (try 264 first, then 260)
            publisher_elem = self._extract_marc_field(record, ns, ["264", "260"], "b")
            publisher = publisher_elem.text if publisher_elem is not None else ""

            # Extract place (try 264 first, then 260)
            place_elem = self._extract_marc_field(record, ns, ["264", "260"], "a")
            place = place_elem.text if place_elem is not None else ""

            # Extract edition statement from field 250$a
            edition_elem = record.find(".//datafield[@tag='250']/subfield[@code='a']")
            if edition_elem is None:
                edition_elem = record.find(
                    ".//marc:datafield[@tag='250']/marc:subfield[@code='a']", ns
                )
            edition = edition_elem.text if edition_elem is not None else ""

            # Extract record ID
            control_001 = record.find(".//controlfield[@tag='001']")
            if control_001 is None:
                control_001 = record.find(".//marc:controlfield[@tag='001']", ns)
            source_id = control_001.text if control_001 is not None else ""

            # Extract LCCN from field 010$a
            lccn_elem = record.find(".//datafield[@tag='010']/subfield[@code='a']")
            if lccn_elem is None:
                lccn_elem = record.find(
                    ".//marc:datafield[@tag='010']/marc:subfield[@code='a']", ns
                )
            lccn = lccn_elem.text.strip() if lccn_elem is not None and lccn_elem.text else ""

            return Publication(
                title=title,
                author=author,
                main_author=main_author,
                pub_date=pub_date,
                publisher=publisher,
                place=place,
                edition=edition,
                lccn=lccn,
                language_code=language_code,
                source="MARC",
                source_id=source_id,
                country_code=country_code,
                country_classification=country_classification,
            )

        except Exception:
            return None

    def _should_include_record(self, pub: Publication) -> bool:
        """Check if record should be included based on year and country filters"""
        # Check US-only filter first (most restrictive)
        if self.us_only and pub.country_classification != CountryClassification.US:
            return False

        # Check year filters
        if pub.year is None:
            return True  # Include records without years to be safe

        # Check minimum year
        if self.min_year is not None and pub.year < self.min_year:
            return False

        # Check maximum year
        if self.max_year is not None and pub.year > self.max_year:
            return False

        return True
