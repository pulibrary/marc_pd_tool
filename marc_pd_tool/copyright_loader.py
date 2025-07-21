"""Copyright data XML loader for publications"""

# Standard library imports
from logging import getLogger
from pathlib import Path
from re import search
from typing import List
from typing import Optional
import xml.etree.ElementTree as ET

# Local imports
from marc_pd_tool.publication import Publication

logger = getLogger(__name__)


class CopyrightDataLoader:
    def __init__(self, copyright_dir: str):
        self.copyright_dir = Path(copyright_dir)

    def load_all_copyright_data(self) -> List[Publication]:
        """Load all copyright data (no year indexing)"""
        logger.info("Loading all copyright data...")

        all_publications = []
        xml_files = sorted(self.copyright_dir.rglob("*.xml"), key=lambda x: str(x))
        logger.info(f"Found {len(xml_files)} XML files in copyright directory")

        batch_start_count = 0
        for i, xml_file in enumerate(xml_files):
            if i % 10 == 0:
                batch_start_count = len(all_publications)
                end_file = min(i + 10, len(xml_files))
                logger.debug(
                    f"Processing copyright files {i+1}-{end_file}/{len(xml_files)}: starting with {xml_file.name}"
                )

            pubs = self._extract_from_file(xml_file)
            all_publications.extend(pubs)

            # Log summary after completing each batch of 10 (or at the end)
            if (i + 1) % 10 == 0 or i == len(xml_files) - 1:
                batch_entries = len(all_publications) - batch_start_count
                files_in_batch = (
                    min(10, len(xml_files) - (i // 10) * 10) if i == len(xml_files) - 1 else 10
                )
                logger.debug(
                    f"  Completed {files_in_batch} files: {batch_entries:,} entries from this batch (Total: {len(all_publications):,})"
                )

        logger.info(
            f"Loaded {len(all_publications):,} copyright entries from {len(xml_files)} files"
        )
        return all_publications

    def _extract_year_from_filename(self, filename: str) -> str:
        year_match = search(r"\b(19|20)\d{2}\b", filename)
        return year_match.group() if year_match else ""

    def _extract_from_file(self, xml_file: Path) -> List[Publication]:
        publications = []

        try:
            tree = ET.parse(xml_file)
            root = tree.getroot()

            for entry in root.findall(".//copyrightEntry"):
                pub = self._extract_from_entry(entry)
                if pub:
                    publications.append(pub)

        except Exception as e:
            logger.warning(f"Error parsing {xml_file}: {e}")

        return publications

    def _extract_from_entry(self, entry) -> Optional[Publication]:
        try:
            # Extract title
            title_elem = entry.find(".//title")
            title = title_elem.text if title_elem is not None else ""

            if not title:
                return None

            # Extract author
            author_elem = entry.find(".//author/authorName")
            author = author_elem.text if author_elem is not None else ""

            # Extract publication date - try multiple sources
            pub_date = ""

            # First try publication date
            pub_date_elem = entry.find(".//publisher/pubDate")
            if pub_date_elem is not None:
                pub_date = pub_date_elem.get("date", pub_date_elem.text or "")

            # If no publication date, try registration date
            if not pub_date:
                reg_date_elem = entry.find(".//regDate")
                if reg_date_elem is not None:
                    pub_date = reg_date_elem.get("date", reg_date_elem.text or "")

            # If still no date, try affidavit date
            if not pub_date:
                aff_date_elem = entry.find(".//affDate")
                if aff_date_elem is not None:
                    pub_date = aff_date_elem.get("date", aff_date_elem.text or "")

            # Extract publisher
            publisher_elem = entry.find(".//publisher/pubName")
            publisher = publisher_elem.text if publisher_elem is not None else ""

            # Extract place
            place_elem = entry.find(".//publisher/pubPlace")
            place = place_elem.text if place_elem is not None else ""

            # Extract volume information from <vol> tag
            vol_elem = entry.find(".//vol")
            volume_info = vol_elem.text if vol_elem is not None else ""

            # Parse volume info to extract part number and name
            part_number = ""
            part_name = ""
            if volume_info:
                # Handle formats like "Vol.3", "Vol.5", "Volume 2", etc.
                volume_info_clean = volume_info.strip()
                if volume_info_clean.lower().startswith(("vol.", "vol ", "volume ")):
                    # Extract the number/name after "Vol." or "Volume"
                    if volume_info_clean.lower().startswith("vol."):
                        part_info = volume_info_clean[4:].strip()
                    elif volume_info_clean.lower().startswith("vol "):
                        part_info = volume_info_clean[4:].strip()
                    else:  # starts with "volume "
                        part_info = volume_info_clean[7:].strip()

                    # Use the extracted info as part_number for now
                    # (could be more sophisticated parsing later)
                    part_number = part_info
                else:
                    # If it doesn't start with Vol/Volume, use the whole thing
                    part_number = volume_info_clean

            # Extract entry ID
            source_id = entry.get("id", entry.get("regnum", ""))

            return Publication(
                title=title,
                author=author,
                main_author="",  # Copyright data doesn't have separate main author field
                pub_date=pub_date,
                publisher=publisher,
                place=place,
                part_number=part_number,  # Extracted from <vol> tag
                part_name=part_name,  # Currently empty, could be enhanced
                source="Copyright",
                source_id=source_id,
            )

        except Exception as e:
            return None
